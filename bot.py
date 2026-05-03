import asyncio
import json
import os
import random
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import discord
from discord.ext import commands


TOKEN_ENV_NAME = "DISCORD_TOKEN"
ADMIN_IDS_ENV_NAME = "ADMIN_USER_IDS"
ADMIN_CHANNEL_ID_ENV_NAME = "ADMIN_CHANNEL_ID"
DATA_FILE = Path(__file__).with_name("restaurants.json")
BACKUP_DIR = Path(__file__).with_name("backups")
ALLOWED_MAP_HOSTS = {
    "naver": ("map.naver.com", "naver.me", "m.place.naver.com", "place.naver.com"),
    "kakao": ("map.kakao.com", "place.map.kakao.com", "kko.to"),
    "google": ("google.com", "www.google.com", "maps.google.com", "maps.app.goo.gl"),
}
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
data_lock = asyncio.Lock()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_admin_ids():
    raw = os.environ.get(ADMIN_IDS_ENV_NAME, "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def is_admin(ctx):
    admin_ids = get_admin_ids()
    if str(ctx.author.id) in admin_ids:
        return True
    permissions = getattr(ctx.author, "guild_permissions", None)
    return bool(permissions and permissions.manage_guild)


def is_admin_interaction(interaction):
    admin_ids = get_admin_ids()
    if str(interaction.user.id) in admin_ids:
        return True
    permissions = getattr(interaction.user, "guild_permissions", None)
    return bool(permissions and permissions.manage_guild)


def load_restaurants():
    if not DATA_FILE.exists():
        return []
    with DATA_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError("restaurants.json must contain a list.")
    return data


def save_restaurants(restaurants):
    BACKUP_DIR.mkdir(exist_ok=True)
    if DATA_FILE.exists():
        backup_name = f"restaurants-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.json"
        shutil.copy2(DATA_FILE, BACKUP_DIR / backup_name)

    temp_file = DATA_FILE.with_suffix(".json.tmp")
    with temp_file.open("w", encoding="utf-8") as file:
        json.dump(restaurants, file, ensure_ascii=False, indent=2)
        file.write("\n")
    temp_file.replace(DATA_FILE)


def normalize_url(url):
    url = url.strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = f"https://{url}"
    return url


def detect_map_provider(url):
    parsed = urlparse(normalize_url(url))
    host = parsed.netloc.lower()
    if not host:
        return None

    for provider, allowed_hosts in ALLOWED_MAP_HOSTS.items():
        if any(host == allowed or host.endswith(f".{allowed}") for allowed in allowed_hosts):
            return provider
    return None


def is_valid_image_url(url):
    if not url:
        return True
    parsed = urlparse(normalize_url(url))
    if parsed.scheme not in {"http", "https"}:
        return False

    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if path.endswith(IMAGE_EXTENSIONS) or "cdn.discordapp.com" in host:
        return True

    query = parse_qs(parsed.query)
    nested_sources = query.get("src", []) + query.get("url", [])
    for nested_source in nested_sources:
        nested_url = unquote(nested_source)
        nested_path = urlparse(nested_url).path.lower()
        if nested_path.endswith(IMAGE_EXTENSIONS):
            return True

    return False


def make_restaurant_id(name, area):
    clean = re.sub(r"[^0-9A-Za-z가-힣]+", "-", f"{area}-{name}").strip("-").lower()
    suffix = uuid.uuid4().hex[:6]
    return f"{clean}-{suffix}" if clean else f"restaurant-{suffix}"


def parse_report(content, attachments):
    parts = [part.strip() for part in content.split("|")]
    if len(parts) < 3:
        raise ValueError(
            "형식: `!맛집제보 이름 | 위치 | 지도링크` 또는 "
            "`!맛집제보 이름 | 위치 | 분류 | 대표메뉴 | 지도링크 | 이미지URL | 설명`"
        )

    if len(parts) >= 5:
        name, area, category, signature_menu, map_url = parts[:5]
        image_url = parts[5] if len(parts) >= 6 else ""
        description = " | ".join(parts[6:]).strip() if len(parts) >= 7 else ""
    else:
        name, area, map_url = parts[:3]
        category = ""
        signature_menu = ""
        image_url = parts[3] if len(parts) >= 4 else ""
        description = " | ".join(parts[4:]).strip() if len(parts) >= 5 else ""

    if not image_url and attachments:
        image_url = attachments[0].url

    name = name.strip()
    area = area.strip()
    map_url = normalize_url(map_url)
    image_url = normalize_url(image_url) if image_url else ""
    provider = detect_map_provider(map_url)

    if not name or not area:
        raise ValueError("이름과 위치는 필수예요.")
    if not provider:
        raise ValueError("지도 링크는 네이버/카카오/구글 지도 링크만 등록할 수 있어요.")
    if image_url and not is_valid_image_url(image_url):
        raise ValueError("이미지는 jpg/png/webp/gif URL 또는 디스코드 첨부 이미지로 등록해주세요.")

    return {
        "name": name,
        "area": area,
        "category": category.strip(),
        "signature_menu": signature_menu.strip(),
        "description": description,
        "image_url": image_url,
        "map": {
            "provider": provider,
            "url": map_url,
        },
    }


def parse_paired_field(value):
    left, _, right = value.partition("|")
    return left.strip(), right.strip()


def parse_image_description(value):
    value = value.strip()
    if not value:
        return "", ""

    if "|" in value:
        image_url, description = parse_paired_field(value)
        return image_url, description

    if re.match(r"^https?://", value, re.IGNORECASE):
        return value, ""

    return "", value


def build_report(name, area, category_menu, map_url, image_description):
    category, signature_menu = parse_paired_field(category_menu)
    image_url, description = parse_image_description(image_description)
    map_url = normalize_url(map_url)
    image_url = normalize_url(image_url) if image_url else ""
    provider = detect_map_provider(map_url)

    if not name.strip() or not area.strip():
        raise ValueError("이름과 위치는 필수예요.")
    if not provider:
        raise ValueError("지도 링크는 네이버/카카오/구글 지도 링크만 등록할 수 있어요.")
    if image_url and not is_valid_image_url(image_url):
        raise ValueError("이미지는 jpg/png/webp/gif URL 또는 디스코드 첨부 이미지로 등록해주세요.")

    return {
        "name": name.strip(),
        "area": area.strip(),
        "category": category,
        "signature_menu": signature_menu,
        "description": description,
        "image_url": image_url,
        "map": {
            "provider": provider,
            "url": map_url,
        },
    }


def add_pending_report(report, user):
    restaurants = load_restaurants()
    created_at = now_iso()
    report.update(
        {
            "id": make_restaurant_id(report["name"], report["area"]),
            "submitted_by": {
                "user_id": str(user.id),
                "display_name": user.display_name,
            },
            "status": "pending",
            "created_at": created_at,
            "updated_at": created_at,
        }
    )
    restaurants.append(report)
    save_restaurants(restaurants)
    return report


def set_report_status(restaurant_id, status):
    restaurants = load_restaurants()
    restaurant = find_restaurant(restaurants, restaurant_id)
    if not restaurant:
        return None
    restaurant["status"] = status
    restaurant["updated_at"] = now_iso()
    save_restaurants(restaurants)
    return restaurant


def restaurant_summary(restaurant):
    chunks = [restaurant.get("area", ""), restaurant.get("name", "이름 없음")]
    if restaurant.get("signature_menu"):
        chunks.append(f"({restaurant['signature_menu']})")
    return " ".join(chunk for chunk in chunks if chunk)


def restaurant_embed(restaurant, title="서강대 맛집 추천"):
    name = restaurant.get("name", "이름 없음")
    embed = discord.Embed(title=title, description=f"**{name}**", color=0x2F855A)
    embed.add_field(name="위치", value=restaurant.get("area") or "정보 없음", inline=True)
    embed.add_field(name="분류", value=restaurant.get("category") or "정보 없음", inline=True)
    embed.add_field(name="대표 메뉴", value=restaurant.get("signature_menu") or "정보 없음", inline=True)

    if restaurant.get("description"):
        embed.add_field(name="설명", value=restaurant["description"], inline=False)

    map_info = restaurant.get("map") or {}
    map_url = map_info.get("url")
    provider = map_info.get("provider") or "지도"
    embed.add_field(name="지도", value=f"[{provider} 지도에서 보기]({map_url})" if map_url else "준비 중", inline=False)

    image_url = restaurant.get("image_url")
    if image_url:
        embed.set_image(url=image_url)

    embed.set_footer(text=f"ID: {restaurant.get('id', 'unknown')}")
    return embed


def report_embed(restaurant, title="새 맛집 제보"):
    embed = restaurant_embed(restaurant, title=title)
    submitter = restaurant.get("submitted_by") or {}
    if submitter:
        embed.add_field(
            name="제보자",
            value=f"{submitter.get('display_name', '알 수 없음')} ({submitter.get('user_id', 'unknown')})",
            inline=False,
        )
    embed.add_field(name="상태", value=restaurant.get("status", "unknown"), inline=True)
    return embed


def find_restaurant(restaurants, restaurant_id):
    for restaurant in restaurants:
        if restaurant.get("id") == restaurant_id:
            return restaurant
    return None


async def notify_admin_channel(restaurant):
    channel_id = os.environ.get(ADMIN_CHANNEL_ID_ENV_NAME, "").strip()
    if not channel_id:
        return

    try:
        channel = bot.get_channel(int(channel_id)) or await bot.fetch_channel(int(channel_id))
    except (ValueError, discord.DiscordException):
        return

    await channel.send(embed=report_embed(restaurant), view=ApprovalView(restaurant["id"]))


class ReportStartView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="맛집 제보하기", style=discord.ButtonStyle.green, custom_id="restaurant_report:start")
    async def open_report_modal(self, interaction, button):
        await interaction.response.send_modal(RestaurantReportModal())


class RestaurantReportModal(discord.ui.Modal, title="맛집 제보"):
    name = discord.ui.TextInput(
        label="맛집 이름",
        placeholder="예: 수라",
        max_length=80,
    )
    area = discord.ui.TextInput(
        label="위치",
        placeholder="예: 정문, 후문, 신촌, 대흥, 광흥창",
        max_length=40,
    )
    category_menu = discord.ui.TextInput(
        label="분류 | 대표메뉴",
        placeholder="예: 한식 | 제육볶음",
        required=False,
        max_length=100,
    )
    map_url = discord.ui.TextInput(
        label="네이버/카카오/구글 지도 링크",
        placeholder="https://map.naver.com/...",
        max_length=500,
    )
    image_description = discord.ui.TextInput(
        label="이미지 URL 또는 설명",
        placeholder="예: 가성비 좋은 한식집 / https://...jpg | 설명",
        required=False,
        style=discord.TextStyle.paragraph,
        max_length=800,
    )

    async def on_submit(self, interaction):
        try:
            report = build_report(
                self.name.value,
                self.area.value,
                self.category_menu.value,
                self.map_url.value,
                self.image_description.value,
            )
        except ValueError as error:
            await interaction.response.send_message(str(error), ephemeral=True)
            return

        async with data_lock:
            report = add_pending_report(report, interaction.user)

        await interaction.response.send_message(
            f"제보가 등록됐어요. 관리자가 승인하면 추천 목록에 추가됩니다.\nID: `{report['id']}`",
            ephemeral=True,
        )
        await notify_admin_channel(report)

    async def on_error(self, interaction, error):
        print(f"맛집 제보 Modal 오류: {error!r}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "제보 저장 중 오류가 났어요. 잠시 뒤 다시 시도해주세요.",
                ephemeral=True,
            )


class ApprovalView(discord.ui.View):
    def __init__(self, restaurant_id):
        super().__init__(timeout=None)
        self.restaurant_id = restaurant_id

    async def update_status(self, interaction, status):
        if not is_admin_interaction(interaction):
            await interaction.response.send_message("이 버튼은 관리자만 사용할 수 있어요.", ephemeral=True)
            return

        async with data_lock:
            restaurant = set_report_status(self.restaurant_id, status)

        if not restaurant:
            await interaction.response.send_message("해당 ID의 제보를 찾지 못했어요.", ephemeral=True)
            return

        for item in self.children:
            item.disabled = True

        label = "승인됨" if status == "approved" else "거절됨"
        await interaction.response.edit_message(
            content=f"{label}: `{self.restaurant_id}`",
            embed=report_embed(restaurant, title=f"맛집 제보 {label}"),
            view=self,
        )

    @discord.ui.button(label="승인", style=discord.ButtonStyle.green, custom_id="restaurant_report:approve")
    async def approve(self, interaction, button):
        await self.update_status(interaction, "approved")

    @discord.ui.button(label="거절", style=discord.ButtonStyle.danger, custom_id="restaurant_report:reject")
    async def reject(self, interaction, button):
        await self.update_status(interaction, "rejected")


@bot.event
async def on_ready():
    if not getattr(bot, "persistent_views_added", False):
        bot.add_view(ReportStartView())
        bot.persistent_views_added = True
    print(f"봇 로그인 성공: {bot.user} ({bot.user.id})")


@bot.command(name="점메추")
async def recommend_lunch(ctx, *, area: str = ""):
    restaurants = load_restaurants()
    approved = [item for item in restaurants if item.get("status") == "approved"]
    if area:
        approved = [item for item in approved if item.get("area", "").lower() == area.lower()]

    if not approved:
        await ctx.send("아직 추천할 맛집 데이터가 없어요. `!맛집제보 이름 | 위치 | 지도링크`로 제보해주세요.")
        return

    await ctx.send(embed=restaurant_embed(random.choice(approved)))


@bot.command(name="맛집")
async def list_restaurants(ctx, *, area: str = ""):
    if area.strip() == "제보":
        await send_report_prompt(ctx)
        return

    restaurants = load_restaurants()
    approved = [item for item in restaurants if item.get("status") == "approved"]
    if area:
        approved = [item for item in approved if item.get("area", "").lower() == area.lower()]

    if not approved:
        await ctx.send("조건에 맞는 맛집이 아직 없어요.")
        return

    lines = [f"- `{item['id']}` {restaurant_summary(item)}" for item in approved[:20]]
    if len(approved) > 20:
        lines.append(f"...외 {len(approved) - 20}개")
    await ctx.send("서강대 주변 맛집 리스트\n" + "\n".join(lines))


@bot.command(name="맛집상세")
async def restaurant_detail(ctx, restaurant_id: str):
    restaurant = find_restaurant(load_restaurants(), restaurant_id)
    if not restaurant or restaurant.get("status") != "approved":
        await ctx.send("해당 ID의 승인된 맛집을 찾지 못했어요.")
        return
    await ctx.send(embed=restaurant_embed(restaurant, title="맛집 상세"))


async def send_report_prompt(ctx):
    await ctx.send(
        "아래 버튼을 눌러 맛집을 제보해주세요.\n"
        "텍스트로도 가능해요: `!맛집제보 이름 | 위치 | 지도링크`",
        view=ReportStartView(),
    )


@bot.command(name="맛집제보", aliases=["제보"])
async def report_restaurant(ctx, *, content: str = ""):
    if not content:
        await send_report_prompt(ctx)
        return

    try:
        report = parse_report(content, list(ctx.message.attachments))
    except ValueError as error:
        await ctx.send(str(error))
        return

    async with data_lock:
        report = add_pending_report(report, ctx.author)

    await ctx.send(
        f"제보가 등록됐어요. 관리자가 확인하면 추천 목록에 추가됩니다.\n"
        f"ID: `{report['id']}`"
    )
    await notify_admin_channel(report)


@bot.command(name="제보목록")
async def list_reports(ctx):
    if not is_admin(ctx):
        await ctx.send("이 명령은 관리자만 사용할 수 있어요.")
        return

    pending = [item for item in load_restaurants() if item.get("status") == "pending"]
    if not pending:
        await ctx.send("대기 중인 제보가 없어요.")
        return

    await ctx.send(f"대기 중인 맛집 제보 {len(pending)}개")
    for item in pending[:10]:
        await ctx.send(embed=report_embed(item), view=ApprovalView(item["id"]))
    if len(pending) > 10:
        await ctx.send(f"한 번에 10개만 표시했어요. 남은 제보: {len(pending) - 10}개")


@bot.command(name="제보승인")
async def approve_report(ctx, restaurant_id: str):
    if not is_admin(ctx):
        await ctx.send("이 명령은 관리자만 사용할 수 있어요.")
        return

    async with data_lock:
        restaurant = set_report_status(restaurant_id, "approved")
        if not restaurant:
            await ctx.send("해당 ID의 제보를 찾지 못했어요.")
            return

    await ctx.send(f"승인 완료: `{restaurant_id}`")


@bot.command(name="제보거절")
async def reject_report(ctx, restaurant_id: str):
    if not is_admin(ctx):
        await ctx.send("이 명령은 관리자만 사용할 수 있어요.")
        return

    async with data_lock:
        restaurant = set_report_status(restaurant_id, "rejected")
        if not restaurant:
            await ctx.send("해당 ID의 제보를 찾지 못했어요.")
            return

    await ctx.send(f"거절 완료: `{restaurant_id}`")


@bot.command(name="도움말")
async def help_command(ctx):
    await ctx.send(
        "명령어\n"
        "- `!점메추` 또는 `!점메추 정문`: 랜덤 추천\n"
        "- `!맛집` 또는 `!맛집 신촌`: 맛집 목록\n"
        "- `!맛집상세 맛집ID`: 상세 정보\n"
        "- `!맛집제보`: 버튼과 입력창으로 맛집 제보\n"
        "- `!맛집제보 이름 | 위치 | 지도링크`: 텍스트로 맛집 제보\n"
        "- `!제보목록`: 관리자 승인 UI 보기"
    )


def main():
    token = os.environ.get(TOKEN_ENV_NAME)
    if not token:
        raise RuntimeError(f"{TOKEN_ENV_NAME} environment variable is not set.")

    bot.run(token)


if __name__ == "__main__":
    main()
