# GCP Codex SSH Setup

This workspace is prepared for developing the Discord bot on a Google Cloud VM from Codex.

## Installed locally

- Google Cloud CLI: installed with `winget`
- Git: already available
- OpenSSH: already available

If `gcloud` is not recognized in an already-open terminal, open a new PowerShell window. The helper scripts in this folder work even before the current terminal picks up the new PATH.

## First-time login

Run this from PowerShell in this folder:

```powershell
.\gcp-login.ps1
```

If script execution is blocked by PowerShell policy, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\gcp-login.ps1
```

## Select your GCP project and zone

```powershell
.\gcp-set-project.ps1 -ProjectId "YOUR_PROJECT_ID" -Zone "asia-northeast3-a"
```

Change the zone to the VM's actual zone.

## SSH into the VM

For this Discord bot VM:

```powershell
.\bot-ssh.ps1
```

Run a single remote command on the bot VM:

```powershell
.\bot-ssh.ps1 -RemoteCommand "pwd && ls"
```

The VM defaults are:

- Project: `my-discord-bot-495213`
- Zone: `us-west1-b`
- Instance: `instance-20260503-133643`

Generic SSH helper:

```powershell
.\gcp-ssh.ps1 -Instance "YOUR_INSTANCE_NAME"
```

Or pass project and zone explicitly:

```powershell
.\gcp-ssh.ps1 -ProjectId "YOUR_PROJECT_ID" -Zone "asia-northeast3-a" -Instance "YOUR_INSTANCE_NAME"
```

Run a single remote command:

```powershell
.\gcp-ssh.ps1 -Instance "YOUR_INSTANCE_NAME" -RemoteCommand "pwd && ls"
```

## Notes

The `.gcloud` directory is local to this workspace and ignored by Git because it can contain credentials.

## Bot service on the VM

The bot now runs as a systemd service:

```bash
sudo systemctl status discord-sogang-bot.service
sudo journalctl -u discord-sogang-bot.service -f
sudo systemctl restart discord-sogang-bot.service
```

Remote project path:

```text
/home/seungminlee1013/discord-sogang-bot
```

Restaurant data:

```text
/home/seungminlee1013/discord-sogang-bot/restaurants.json
```

The Discord token is stored in:

```text
/home/seungminlee1013/discord-sogang-bot/.env
```

## Discord commands

```text
!점메추
!점메추 정문
!맛집
!맛집 신촌
!맛집상세 맛집ID
!맛집제보
!맛집제보 이름 | 위치 | 지도링크
!맛집제보 이름 | 위치 | 분류 | 대표메뉴 | 지도링크 | 이미지URL | 설명
!제보목록
!제보승인 맛집ID
!제보거절 맛집ID
!맛집관리
!추천 자연어질문
!도움말
```

Admin commands are available to users with Discord `Manage Server` permission, or user IDs listed in `ADMIN_USER_IDS` inside `.env`.

`!맛집제보` opens a Discord button and modal form. `!제보목록` shows pending reports with approve/reject buttons.

`!맛집관리` opens an admin-only Discord UI for:

- Adding an approved restaurant
- Editing an existing restaurant
- Archiving a restaurant so it disappears from recommendations
- Toggling visibility between `approved` and `hidden`
- Opening pending report approval cards

`!추천` uses Supabase pgvector + Gemini API when configured. Without those environment variables, the rest of the bot continues to run in JSON mode.

Example:

```text
!추천 교정 중이라 부드러운 음식 먹고 싶어
!추천 선배님께 밥보은할 조용한 일식집
```

Optional `.env` value:

```text
ADMIN_CHANNEL_ID=123456789012345678
```

When set, new reports are posted to that channel with approve/reject buttons automatically.

Optional RAG values:

```text
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key
GEMINI_API_KEY=your_gemini_api_key
GEMINI_GENERATION_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_EMBEDDING_DIMENSIONS=768
```

Supabase setup SQL is in `supabase_schema.sql`. After configuring `.env`, migrate the existing JSON data with:

Run `supabase_schema.sql` once in the Supabase SQL Editor first. The bot's `SUPABASE_SERVICE_ROLE_KEY` can read/write rows, but it cannot create the database schema by itself through PostgREST.

```powershell
$env:MIGRATION_GUILD_ID="YOUR_DISCORD_SERVER_ID"
python .\scripts\migrate_json_to_supabase.py
```
