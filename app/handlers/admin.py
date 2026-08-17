import asyncio
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router=Router()

async def guard(message, admin):
    return await admin.is_sudo(message.from_user.id)

@router.message(Command("admin"))
async def admin_panel(message, admin):
    if not await guard(message,admin): return
    await message.answer(
        "🛡 <b>ADMIN PANEL</b>\n\n/sudo list\n/sudo add USER_ID\n/sudo remove USER_ID\n"
        "/broadcast TEXT\n/maintenance on|off", parse_mode="HTML")

@router.message(Command("sudo"))
async def sudo(message, admin):
    if message.from_user.id!=admin.owner_id:
        await message.answer("❌ Owner only."); return
    p=(message.text or "").split(); action=p[1].lower() if len(p)>1 else "list"
    if action=="list":
        rows=await admin.list_sudo()
        await message.answer("🛡 <b>SUDO</b>\n\n"+("\n".join(f"• {r['_id']}" for r in rows) or "No sudo users."),
                             parse_mode="HTML"); return
    if len(p)!=3 or not p[2].isdigit():
        await message.answer("Usage: /sudo add|remove USER_ID"); return
    uid=int(p[2])
    if action=="add": await message.answer("✅ Sudo added." if await admin.add_sudo(uid) else "ℹ️ Already sudo.")
    elif action=="remove": await message.answer("✅ Sudo removed." if await admin.remove_sudo(uid) else "ℹ️ Not found.")
    else: await message.answer("Use add, remove or list.")

@router.message(Command("broadcast"))
async def broadcast(message: Message, admin, bot):
    if not await guard(message,admin): return
    text=(message.text or "").partition(" ")[2].strip()
    if not text:
        await message.answer("Usage: /broadcast TEXT"); return
    sent=failed=0
    for chat_id in await admin.chat_ids():
        try:
            await bot.send_message(chat_id,text); sent+=1; await asyncio.sleep(0.05)
        except Exception: failed+=1
    await message.answer(f"📣 Broadcast complete.\n\n✅ {sent} sent\n❌ {failed} failed")

@router.message(Command("maintenance"))
async def maintenance(message: Message, admin):
    if not await guard(message,admin): return
    p=(message.text or "").split(); mode=p[1].lower() if len(p)>1 else ""
    if mode not in {"on","off"}:
        await message.answer("Usage: /maintenance on|off"); return
    await admin.set_maintenance(mode=="on")
    await message.answer(f"🛠 Maintenance <b>{mode.upper()}</b>",parse_mode="HTML")
