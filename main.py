import discord
from discord.ext import commands, tasks
from discord import ui, ButtonStyle, app_commands
from datetime import datetime, timedelta
import json
import io
import asyncio
import os
import re
import random


CONFIG_FILE = "modbot_config.json"
WARNINGS_FILE = "user_warnings.json"
BAD_WORDS = [
    "fuck", "shit", "bitch", "asshole", "bastard", "cunt",
    "retard", "slut", "whore", "dick", "pussy", "penis",
    "vagina", "sex", "porn", "nigger", "faggot", "gaysex"
]
FUNNY_NOTES = [
    "Certified profile picture moment",
    "Avatar powered by 100% cringe-free pixels",
    "Warning: May cause envy",
    "This face has +10 charisma",
    "Do not feed after midnight",
    "Too iconic to ignore",
    "Caution: dripping in 4K",
    "Smile increases server morale by +5",
    "Face reveal DLC unlocked",
    "Pixels trained by comedians",
    "Avatar so crisp it needs sunglasses",
    "Certified fresh pixels",
    "Zoom in for hidden easter eggs",
    "Warning: may attract compliments",
    "Elegance detected — proceed with admiration",
]


def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


config = load_json(CONFIG_FILE, {})
warnings_store = load_json(WARNINGS_FILE, {})
soft_mutes = {}


def save_config(): save_json(CONFIG_FILE, config)
def save_warnings(): save_json(WARNINGS_FILE, warnings_store)


def ensure_list(key):
    if key not in warnings_store:
        warnings_store[key] = []


def get_mod_role(guild):
    role_id = config.get(str(guild.id), {}).get("mod_role_id")
    return guild.get_role(role_id) if role_id else None


def get_mod_bypass_role(guild):
    bypass_id = config.get(str(guild.id), {}).get("bypass_role_id")
    return guild.get_role(bypass_id) if bypass_id else None


def get_log_channel(guild):
    channel_id = config.get(str(guild.id), {}).get("log_channel_id")
    return guild.get_channel(channel_id) if channel_id else None


def is_mod(member):
    mod_role = get_mod_role(member.guild)
    return mod_role in member.roles or member.guild_permissions.administrator

def build_help_embed(user, guild):
    embed = discord.Embed(title="Your Available Commands", color=0x3498DB)
    embed.set_author(name=f"{user}", icon_url=getattr(getattr(user, "avatar", None), "url", None))
    can_admin = getattr(getattr(user, "guild_permissions", None), "administrator", False)
    can_manage = getattr(getattr(user, "guild_permissions", None), "manage_messages", False)
    mod_role = get_mod_role(guild) if guild else None
    has_mod_role = bool(mod_role and hasattr(user, "roles") and mod_role in user.roles)
    general = []
    general.append("/help | !help – Show your commands")
    general.append("/userinfo <user> | !userinfo <user> – View user info")
    general.append("/avatar <user> | !avatar <user> – Show avatar")
    general.append("/roleinfo <role> | !roleinfo <role> – View role info")
    general.append("/serverinfo | !serverinfo – View server info")
    embed.add_field(name="General", value="\n".join(general), inline=False)
    moderation = []
    if has_mod_role:
        moderation.append("/moderate <user> | !moderate – Open moderation panel")
        moderation.append("/purge <amount> | !purge <amount> – Delete messages")
        moderation.append("/warn <user> <reason> | !warn <user> <reason> – Warn user")
        moderation.append("/kick <user> <reason> | !kick <user> <reason> – Kick user")
        moderation.append("/ban <user> <duration> <reason> | !ban <user> <duration> <reason> – Ban user")
        moderation.append("/unban <user> | !unban <id|username> – Unban user")
        moderation.append("/mute <user> <duration> <reason> | !mute <user> <duration> <reason> – Timeout user")
        moderation.append("/unmute <user> | !unmute <user> – Remove timeout")
        moderation.append("/addrole <user> <role> | !addrole <user> <role> – Add role")
        moderation.append("/removerole <user> <role> | !removerole <user> <role> – Remove role")
    if moderation:
        embed.add_field(name="Moderation", value="\n".join(moderation), inline=False)
    config_cmds = []
    if can_admin:
        config_cmds.append("/setup | !setup – Guided setup panel")
        config_cmds.append("/setmod <role> | !setmod – Set mod role")
        config_cmds.append("/setlog <channel> | !setlog – Set log channel")
        config_cmds.append("/setmodbypass <role> | !setmodbypass – Set AutoMod bypass role")
        config_cmds.append("/startautomod | !startautomod – Enable AutoMod")
        config_cmds.append("/stopautomod | !stopautomod – Disable AutoMod")
    if config_cmds:
        embed.add_field(name="Configuration", value="\n".join(config_cmds), inline=False)
    embed.set_footer(text=f"User: {getattr(user, 'name', str(user))} • {time_now()}", icon_url=getattr(getattr(user, "avatar", None), "url", None))
    return embed


def time_now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


def normalize(text):
    s = text.lower()
    s = re.sub(r'[\u200B-\u200D\uFEFF]', '', s)
    table = str.maketrans({
        '@': 'a', '$': 's', '!': 'i', '1': 'i', '3': 'e', '4': 'a',
        '5': 's', '7': 't', '0': 'o', '8': 'b', '&': 'and'
    })
    s = s.translate(table)
    s = re.sub(r'[^a-z]', '', s)
    s = re.sub(r'(.)\1{2,}', r'\1\1', s)
    return s


def contains_bad_word(raw_content):
    content_norm = normalize(raw_content)
    for bad_word in BAD_WORDS:
        bad_norm = normalize(bad_word)
        if bad_norm in content_norm:
            return bad_word
    return None

def has_invite_link(text):
    s = text.lower()
    return ("discord.gg/" in s) or ("discord.com/invite/" in s)

def count_custom_emotes(text):
    return len(re.findall(r"<a?:\w+:\d+>", text))

def count_unicode_emotes(text):
    return len(re.findall(r"[\U0001F300-\U0001FAFF\U0001F1E6-\U0001F1FF]", text))

def is_excessive_caps(text):
    letters = re.findall(r"[a-zA-Z]", text)
    if len(letters) < 15:
        return False
    uppers = sum(1 for c in letters if c.isupper())
    return (uppers / len(letters)) >= 0.7

async def handle_automod(botinstance, message, action_name, reason_text, color):
    ensure_list(str(message.author.id))
    warnings_store[str(message.author.id)].append({
        "reason": f"AutoMod: {action_name}",
        "moderator_id": botinstance.user.id,
        "timestamp": time_now(),
        "action_id": f"amod-{datetime.utcnow().timestamp()}"
    })
    save_warnings()
    warn_count = len(get_warnings(message.author.id))
    try:
        await message.delete()
    except Exception:
        pass
    log_channel = get_log_channel(message.guild)
    if log_channel:
        embed = botinstance._log_embed(
            action=f"AutoMod: {action_name}",
            moderator=message.guild.me,
            target=message.author,
            reason=reason_text,
            color=color
        )
        await log_channel.send(embed=embed)
        for att in message.attachments[:3]:
            try:
                await log_channel.send(file=await att.to_file())
            except Exception:
                pass
    try:
        dm = ack_embed(botinstance.user, f"AutoMod: {action_name}\nReason: {reason_text}\nServer: {message.guild.name}")
        await message.author.send(embed=dm)
    except Exception:
        pass
    if warn_count == 3:
        await auto_timeout(message.author, message, 15, "Reached 3 warnings: auto timeout")
    elif warn_count == 5:
        await auto_timeout(message.author, message, 60*24, "Reached 5 warnings: auto timeout")


def parse_duration_arg(s: str):
    s = s.lower().strip()
    days = 0
    hours = 0
    md = re.search(r'(\d+)\s*d', s)
    mh = re.search(r'(\d+)\s*h', s)
    if md:
        days = int(md.group(1))
    if mh:
        hours = int(mh.group(1))
    if days == 0 and hours == 0:
        return None
    return timedelta(days=days, hours=hours)


def get_warnings(user_id: int):
    return warnings_store.get(str(user_id), [])


def clear_warnings(user_id: int):
    if str(user_id) in warnings_store:
        warnings_store[str(user_id)] = []
        save_warnings()


async def auto_timeout(member, ctx_or_interaction, duration_minutes, reason):
    until = datetime.utcnow() + timedelta(minutes=duration_minutes)
    soft_mutes[member.id] = until
    moderator_obj = getattr(ctx_or_interaction, "user", None) or getattr(ctx_or_interaction, "author", None) or member.guild.me
    msg = await bot.log_action(member.guild,
        "Auto Timeout (Warn limit)", moderator_obj, member, reason, 0xE67E22, duration=f"{duration_minutes} minutes",
        extra_footer="Action Expires In: updating...")
    if msg:
        mod_name = getattr(moderator_obj, "name", None)
        mod_icon = getattr(getattr(moderator_obj, "avatar", None), "url", None)
        bot.bg_tasks[msg.id] = {"message": msg, "ends": until, "action": "timeout", "mod_name": mod_name, "mod_icon_url": mod_icon}
    try:
        dm = ack_embed(member.guild.me, f"You have been muted for {duration_minutes} minutes. Reason: {reason}")
        await member.send(embed=dm)
    except Exception:
        pass
    if hasattr(ctx_or_interaction, "response"):
        if not ctx_or_interaction.response.is_done():
            emb = ack_embed(getattr(ctx_or_interaction, "user", member.guild.me), f"{member.mention} muted for {duration_minutes} minutes.")
            await ctx_or_interaction.response.send_message(embed=emb, ephemeral=True)
    else:
        emb = ack_embed(getattr(ctx_or_interaction, "author", member.guild.me), f"{member.mention} muted for {duration_minutes} minutes.")
        await ctx_or_interaction.send(embed=emb)


class ModBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=discord.Intents.all(),
            help_command=None
        )
        self.bg_tasks = {}
        self.panels = {}
        self.recent_users = {}


    async def setup_hook(self):
        if not update_panel_timers.is_running():
            update_panel_timers.start(self)
        if not update_log_footers.is_running():
            update_log_footers.start(self)
        try:
            await self.tree.sync()
        except Exception:
            pass


    async def on_ready(self):
        print(f"Bot online as {self.user}.")


    async def on_message(self, message: discord.Message):
        if not message.guild:
            return

        lst = self.recent_users.setdefault(message.guild.id, [])
        try:
            lst.remove(message.author.id)
        except Exception:
            pass
        lst.insert(0, message.author.id)
        if len(lst) > 50:
            del lst[50:]

        now = datetime.utcnow()
        mute_end = soft_mutes.get(message.author.id)
        if mute_end:
            if now >= mute_end:
                soft_mutes.pop(message.author.id, None)
            else:
                try:
                    await message.delete()
                except Exception:
                    pass
                log_channel = get_log_channel(message.guild)
                if log_channel:
                    left_mins = max(0, int((mute_end - now).total_seconds() // 60))
                    embed = self._log_embed(
                        action="Timeout Enforcement",
                        moderator=message.guild.me,
                        target=message.author,
                        reason=f"Deleted message while timed out. Remaining: {left_mins} minutes",
                        color=0x2980B9
                    )
                    await log_channel.send(embed=embed)
                return

        if message.author.bot:
            return
        cfg = config.setdefault(str(message.guild.id), {})
        if cfg.get("automod_enabled", True) is False:
            await self.process_commands(message)
            return
        bypass_role = get_mod_bypass_role(message.guild)
        if bypass_role and bypass_role in message.author.roles:
            return

        if has_invite_link(message.content):
            await handle_automod(self, message, "Invite Link", "Unauthorized invite link detected.", 0xE74C3C)
            return
        urls = re.findall(r'https?://\S+', message.content.lower())
        if len(urls) >= 5:
            await handle_automod(self, message, "Link Spam", f"Detected {len(urls)} links.", 0xE74C3C)
            return
        mentions_total = len(message.mentions) + len(getattr(message, 'role_mentions', [])) + (1 if message.mention_everyone else 0)
        if mentions_total >= 5:
            await handle_automod(self, message, "Mass Mention", f"Detected {mentions_total} mentions.", 0xE67E22)
            return
        if is_excessive_caps(message.content):
            await handle_automod(self, message, "Excessive Caps", "High ratio of capital letters.", 0xE67E22)
            return
        emote_count = count_custom_emotes(message.content) + count_unicode_emotes(message.content)
        if emote_count >= 8:
            await handle_automod(self, message, "Emote Spam", f"Detected {emote_count} emotes.", 0xE67E22)
            return

        bad_word_detected = contains_bad_word(message.content)
        if bad_word_detected:
            ensure_list(str(message.author.id))
            warnings_store[str(message.author.id)].append({
                "reason": f'AutoMod Violation: "{bad_word_detected}"',
                "moderator_id": self.user.id,
                "timestamp": time_now(),
                "action_id": f"amod-{datetime.utcnow().timestamp()}"
            })
            save_warnings()
            warn_count = len(get_warnings(message.author.id))
            if warn_count == 3:
                await auto_timeout(message.author, message, 15, "Reached 3 warnings: auto timeout")
            elif warn_count == 5:
                await auto_timeout(message.author, message, 60*24, "Reached 5 warnings: auto timeout")
            try:
                await message.delete()
            except Exception:
                pass
            log_channel = get_log_channel(message.guild)
            if log_channel:
                embed = self._log_embed(
                    action="AutoMod Warning",
                    moderator=message.guild.me,
                    target=message.author,
                    reason=f'Used: {bad_word_detected}',
                    color=0xE74C3C
                )
                await log_channel.send(embed=embed)
                # re-upload attachments for evidence
                for att in message.attachments[:3]:
                    try:
                        await log_channel.send(file=await att.to_file())
                    except Exception:
                        pass
            try:
                await message.author.send(f"You received an AutoMod warning in {message.guild.name} for inappropriate language.")
            except Exception:
                pass
            return


        await self.process_commands(message)

    def _log_embed(self, action, moderator, target, reason, color, duration=None, extra_footer=None):
        theme_color = color if color else 0x8E44AD
        embed = discord.Embed(title=action, color=theme_color, timestamp=datetime.utcnow())
        embed.set_author(name=f"{moderator.name} ({moderator.id})", icon_url=getattr(moderator.avatar, "url", None))
        avatar_url = getattr(getattr(target, "avatar", None), "url", None)
        if avatar_url:
            embed.set_thumbnail(url=avatar_url)
        user_label = getattr(target, "mention", str(target))
        user_id = getattr(target, "id", "unknown")
        embed.add_field(name="User", value=f"{user_label}\n`{user_id}`", inline=True)
        embed.add_field(name="Reason", value=reason or "No reason provided", inline=True)
        if duration:
            embed.add_field(name="Duration", value=duration, inline=False)
        mod_icon = getattr(getattr(moderator, "avatar", None), "url", None)
        local_stamp = datetime.now().strftime("Today at %I:%M %p")
        footer_text = extra_footer or f"{time_now()} • {local_stamp}"
        embed.set_footer(text=footer_text, icon_url=mod_icon)
        return embed

    async def log_action(self, guild, action, moderator, target, reason, color, duration=None, extra_footer=None):
        log_channel = get_log_channel(guild)
        if log_channel:
            embed = self._log_embed(action, moderator, target, reason, color, duration, extra_footer)
            return await log_channel.send(embed=embed)


bot = ModBot()


# --- Restriction Utilities ---
def cannot_moderate(ctx_user, target_member):
    # Restrict moderating self
    if ctx_user.id == target_member.id:
        return "You cannot moderate yourself."
    # Restrict moderating peers/superiors
    if ctx_user.top_role.position <= target_member.top_role.position and not ctx_user.guild_permissions.administrator:
        return "You cannot moderate a user equal to or above your highest role."
    return None

def require_mod(member):
    return None if is_mod(member) else "You do not have permission to use moderation commands."


class ModPanel(ui.View):
    def __init__(self, target, issuer, bot, timeout=120):
        super().__init__(timeout=timeout)
        self.target = target
        self.issuer = issuer
        self.bot = bot
        self.panel_msg = None
        self.expiry = datetime.utcnow() + timedelta(seconds=timeout)


    async def on_timeout(self):
        if self.panel_msg:
            try:
                await self.panel_msg.delete()
            except Exception:
                pass


    @ui.button(label="Warn", style=ButtonStyle.gray)
    async def warn_btn(self, interaction: discord.Interaction, button: ui.Button):
        perm_msg = require_mod(interaction.user)
        if perm_msg:
            await interaction.response.send_message(perm_msg, ephemeral=True)
            return
        error = cannot_moderate(interaction.user, self.target)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        modal = ReasonModal(self.target, self.issuer, self.bot, "warn", interaction.user)
        await interaction.response.send_modal(modal)


    @ui.button(label="Clear Warns", style=ButtonStyle.green)
    async def clear_warns_btn(self, interaction: discord.Interaction, button: ui.Button):
        perm_msg = require_mod(interaction.user)
        if perm_msg:
            await interaction.response.send_message(perm_msg, ephemeral=True)
            return
        error = cannot_moderate(interaction.user, self.target)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        clear_warnings(self.target.id)
        await interaction.response.send_message(f"Cleared all warnings for {self.target.mention}.", ephemeral=True)
        await self.bot.log_action(interaction.guild, "Warns Cleared", interaction.user, self.target, "All warnings removed", 0x27AE60)


    @ui.button(label="Kick", style=ButtonStyle.red)
    async def kick_btn(self, interaction: discord.Interaction, button: ui.Button):
        perm_msg = require_mod(interaction.user)
        if perm_msg:
            await interaction.response.send_message(perm_msg, ephemeral=True)
            return
        error = cannot_moderate(interaction.user, self.target)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        modal = ReasonModal(self.target, self.issuer, self.bot, "kick", interaction.user)
        await interaction.response.send_modal(modal)


    @ui.button(label="Ban", style=ButtonStyle.red)
    async def ban_btn(self, interaction: discord.Interaction, button: ui.Button):
        perm_msg = require_mod(interaction.user)
        if perm_msg:
            await interaction.response.send_message(perm_msg, ephemeral=True)
            return
        error = cannot_moderate(interaction.user, self.target)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        modal = ReasonDurationModal(self.target, self.issuer, self.bot, "ban", interaction.user)
        await interaction.response.send_modal(modal)


    @ui.button(label="Unban", style=ButtonStyle.green)
    async def unban_btn(self, interaction: discord.Interaction, button: ui.Button):
        perm_msg = require_mod(interaction.user)
        if perm_msg:
            await interaction.response.send_message(perm_msg, ephemeral=True)
            return
        error = cannot_moderate(interaction.user, self.target)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        bans = await interaction.guild.bans()
        entry = next((ban for ban in bans if ban.user.id == self.target.id), None)
        if entry:
            await interaction.guild.unban(entry.user, reason=f"Unbanned via panel by {interaction.user}")
            await interaction.response.send_message(f"{entry.user} unbanned.", ephemeral=True)
            await self.bot.log_action(interaction.guild, "Unban", interaction.user, entry.user, "Unbanned", 0x27AE60)
        else:
            await interaction.response.send_message("User not found in ban list.", ephemeral=True)


    @ui.button(label="Mute (Timeout)", style=ButtonStyle.blurple)
    async def mute_btn(self, interaction: discord.Interaction, button: ui.Button):
        perm_msg = require_mod(interaction.user)
        if perm_msg:
            await interaction.response.send_message(perm_msg, ephemeral=True)
            return
        error = cannot_moderate(interaction.user, self.target)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        modal = ReasonDurationModal(self.target, self.issuer, self.bot, "mute", interaction.user)
        await interaction.response.send_modal(modal)


    @ui.button(label="Unmute (Timeout)", style=ButtonStyle.green)
    async def unmute_btn(self, interaction: discord.Interaction, button: ui.Button):
        perm_msg = require_mod(interaction.user)
        if perm_msg:
            await interaction.response.send_message(perm_msg, ephemeral=True)
            return
        error = cannot_moderate(interaction.user, self.target)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        soft_mutes.pop(self.target.id, None)
        await interaction.response.send_message(f"{self.target.mention}'s timeout removed.", ephemeral=True)
        await self.bot.log_action(interaction.guild, "Unmute", interaction.user, self.target, "Timeout removed", 0x27AE60)

    @ui.button(label="Close Panel", style=ButtonStyle.red)
    async def close_btn(self, interaction: discord.Interaction, button: ui.Button):
        perm_msg = require_mod(interaction.user)
        if perm_msg:
            await interaction.response.send_message(perm_msg, ephemeral=True)
            return
        error = cannot_moderate(interaction.user, self.target)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        try:
            if self.panel_msg:
                await self.panel_msg.delete()
        except Exception:
            pass
        self.bot.panels = {k: v for k, v in self.bot.panels.items() if v is not self}
        await interaction.response.send_message("Panel closed.", ephemeral=True)


    def get_panel_embed(self):
        warns = get_warnings(self.target.id)
        embed = discord.Embed(
            title=f"Moderation Panel for {self.target}",
            color=0x3498DB
        )
        embed.set_thumbnail(url=getattr(self.target.avatar, "url", None))
        embed.add_field(name="User Details",
            value=f"{self.target.mention}\nID: `{self.target.id}`\nStatus: `{str(self.target.status).title()}`",
            inline=False)
        if warns:
            warn_list = "\n".join(
                f"{i+1}. {w['reason']} by `{w['moderator_id']}` on {w['timestamp']}"
                for i, w in enumerate(warns[-3:])
            )
            embed.add_field(name="Warning History", value=f"Warnings: {len(warns)}\n{warn_list}", inline=False)
        else:
            embed.add_field(name="Warning History", value="No active warnings.", inline=False)
        left = self.expiry - datetime.utcnow()
        total_seconds = int(max(left.total_seconds(), 0))
        minutes, seconds = divmod(total_seconds, 60)
        mod_icon = getattr(self.issuer.avatar, "url", None)
        if total_seconds > 0:
            embed.set_footer(text=f"Moderator: {self.issuer.name} • Panel expires in {minutes:02}:{seconds:02}", icon_url=mod_icon)
        else:
            embed.set_footer(text=f"Moderator: {self.issuer.name} • Panel expired!", icon_url=mod_icon)
        return embed


class ReasonModal(ui.Modal, title="Enter Reason"):
    reason = ui.TextInput(label="Reason", style=discord.TextStyle.paragraph, required=True)
    def __init__(self, target, issuer, bot, action, actor):
        super().__init__()
        self.target = target
        self.issuer = issuer
        self.bot = bot
        self.action = action
        self.actor = actor
    async def on_submit(self, interaction: discord.Interaction):
        perm_msg = require_mod(self.actor)
        if perm_msg:
            await interaction.response.send_message(perm_msg, ephemeral=True)
            return
        error = cannot_moderate(self.actor, self.target)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        reason = self.reason.value
        ensure_list(str(self.target.id))
        warnings_store[str(self.target.id)].append({
            "reason": reason,
            "moderator_id": self.issuer.id,
            "timestamp": time_now(),
            "action_id": f"{self.action}-{datetime.utcnow().timestamp()}"
        })
        save_warnings()
        warn_count = len(get_warnings(self.target.id))
        if warn_count == 3:
            await auto_timeout(self.target, interaction, 15, "Reached 3 warnings: auto timeout")
        elif warn_count == 5:
            await auto_timeout(self.target, interaction, 60*24, "Reached 5 warnings: auto timeout")
        await interaction.response.send_message(f"{self.target.mention} warned.", ephemeral=True)
        msg = await self.bot.log_action(interaction.guild,
            "Warn", self.issuer, self.target, reason, color=0xF1C40F,
            extra_footer=f"Warning issued on: {time_now()} | Active Warnings: {warn_count}")
        if msg:
            self.bot.bg_tasks[msg.id] = {"message": msg, "action": "warn", "user_id": self.target.id, "timestamp": time_now(), "mod_name": self.issuer.name, "mod_icon_url": getattr(self.issuer.avatar, "url", None)}
        if self.action == "kick":
            try:
                await self.target.kick(reason=reason)
                await self.bot.log_action(interaction.guild,
                    "Kick", self.issuer, self.target, reason, color=0xE74C3C)
            except Exception:
                pass


class ReasonDurationModal(ui.Modal, title="Enter Reason and Duration"):
    duration_days = ui.TextInput(label="Days", style=discord.TextStyle.short, required=True, default="0")
    duration_hours = ui.TextInput(label="Hours", style=discord.TextStyle.short, required=True, default="1")
    reason = ui.TextInput(label="Reason", style=discord.TextStyle.paragraph, required=True)
    def __init__(self, target, issuer, bot, action, actor):
        super().__init__()
        self.target = target
        self.issuer = issuer
        self.bot = bot
        self.action = action
        self.actor = actor
    async def on_submit(self, interaction: discord.Interaction):
        perm_msg = require_mod(self.actor)
        if perm_msg:
            await interaction.response.send_message(perm_msg, ephemeral=True)
            return
        error = cannot_moderate(self.actor, self.target)
        if error:
            await interaction.response.send_message(error, ephemeral=True)
            return
        try:
            days = int(self.duration_days.value)
            hours = int(self.duration_hours.value)
            duration = timedelta(days=days, hours=hours)
            total_seconds = int(duration.total_seconds())
            if total_seconds <= 0 or total_seconds > 60*60*24*365:
                raise ValueError
        except Exception:
            await interaction.response.send_message("Invalid duration. Use valid integer values.", ephemeral=True)
            return
        reason_val = self.reason.value
        if self.action == "ban":
            try:
                await self.target.ban(reason=reason_val)
                await interaction.response.send_message(f"{self.target.mention} banned for {days}d {hours}h.", ephemeral=True)
                msg = await self.bot.log_action(interaction.guild,
                    "Ban", self.issuer, self.target, reason_val, 0xE74C3C, duration=f"{days}d {hours}h",
                    extra_footer="Action Expires In: updating...")
                self.bot.bg_tasks[msg.id] = {"message": msg, "ends": datetime.utcnow()+duration, "action":"ban", "mod_name": self.issuer.name, "mod_icon_url": getattr(self.issuer.avatar, "url", None)}
            except Exception:
                await interaction.response.send_message("Failed to ban user.", ephemeral=True)
        elif self.action == "mute":
            until = datetime.utcnow() + duration
            soft_mutes[self.target.id] = until
            await interaction.response.send_message(f"{self.target.mention} muted for {days}d {hours}h.", ephemeral=True)
            msg = await self.bot.log_action(interaction.guild,
                "Timeout (Mute)", self.issuer, self.target, reason_val, 0x2980B9, duration=f"{days}d {hours}h",
                extra_footer="Action Expires In: updating...")
            self.bot.bg_tasks[msg.id] = {"message": msg, "ends": until, "action":"timeout", "mod_name": self.issuer.name, "mod_icon_url": getattr(self.issuer.avatar, "url", None)}


class ModerationSelectorView(ui.View):
    def __init__(self, issuer, bot, guild, timeout=120):
        super().__init__(timeout=timeout)
        self.issuer = issuer
        self.bot = bot
        self.guild = guild
        self.selector_msg = None
        self.mode = "recent"  # or "all"
        self._build_select()

    def _build_options(self):
        options = []
        if self.mode == "recent":
            for uid in self.bot.recent_users.get(self.guild.id, [])[:25]:
                m = self.guild.get_member(uid)
                if m:
                    options.append(discord.SelectOption(label=str(m), description=f"ID: {m.id}", value=str(m.id)))
        else:
            # first 25 non-bot members alphabetically
            members = [m for m in self.guild.members if not m.bot]
            members.sort(key=lambda x: (x.display_name or x.name).lower())
            for m in members[:25]:
                options.append(discord.SelectOption(label=str(m), description=f"ID: {m.id}", value=str(m.id)))
        if not options:
            options = [discord.SelectOption(label="No users", value="none")]
        return options

    def _build_select(self):
        options = self._build_options()
        # remove existing select if present
        for child in list(self.children):
            if isinstance(child, ui.Select):
                self.remove_item(child)
        select = ui.Select(placeholder="Select a user", min_values=1, max_values=1, options=options)
        async def _on_select(interaction: discord.Interaction):
            if select.values[0] == "none":
                await interaction.response.send_message("No users available.", ephemeral=True)
                return
            member = interaction.guild.get_member(int(select.values[0]))
            perm_msg = require_mod(interaction.user)
            if perm_msg:
                await interaction.response.send_message(perm_msg, ephemeral=True)
                return
            error = cannot_moderate(interaction.user, member)
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return
            panel = ModPanel(member, self.issuer, self.bot)
            embed = panel.get_panel_embed()
            await interaction.response.send_message(embed=embed, view=panel)
            sent = await interaction.original_response()
            panel.panel_msg = sent
            self.bot.panels[sent.id] = panel
            # delete selector panel after use
            try:
                if self.selector_msg:
                    await self.selector_msg.delete()
            except Exception:
                pass
        select.callback = _on_select
        self.add_item(select)

    def get_embed(self):
        mode_title = "Recent Users" if self.mode == "recent" else "All Users"
        embed = discord.Embed(title=f"Select a user to moderate ({mode_title})", color=0x3498DB)
        embed.set_thumbnail(url=getattr(self.issuer.avatar, "url", None))
        users_lines = []
        options = self._build_options()
        for opt in options[:10]:
            if opt.value == "none":
                continue
            users_lines.append(f"- {opt.label} (`{opt.value}`)")
        list_text = "\n".join(users_lines) if users_lines else "No users to show."
        embed.add_field(name="Users", value=list_text, inline=False)
        embed.description = "Choose from the dropdown, click Search, or toggle Filter to switch lists."
        embed.set_footer(text=f"Moderator: {self.issuer.name} • {time_now()}", icon_url=getattr(self.issuer.avatar, "url", None))
        return embed

    @ui.button(label="Search", style=ButtonStyle.blurple)
    async def search_btn(self, interaction: discord.Interaction, button: ui.Button):
        class SearchModal(ui.Modal, title="Search User"):
            query = ui.TextInput(label="User ID or Username", style=discord.TextStyle.short, required=True)
            def __init__(self, outer):
                super().__init__()
                self.outer = outer
            async def on_submit(self, interaction: discord.Interaction):
                q = self.query.value.strip()
                target = None
                if q.isdigit():
                    target = interaction.guild.get_member(int(q))
                if not target:
                    lower = q.lower()
                    for m in interaction.guild.members:
                        if lower in m.name.lower() or lower in m.display_name.lower():
                            target = m
                            break
                if not target:
                    await interaction.response.send_message("User not found.", ephemeral=True)
                    return
                perm_msg = require_mod(interaction.user)
                if perm_msg:
                    await interaction.response.send_message(perm_msg, ephemeral=True)
                    return
                error = cannot_moderate(interaction.user, target)
                if error:
                    await interaction.response.send_message(error, ephemeral=True)
                    return
                panel = ModPanel(target, self.outer.issuer, self.outer.bot)
                embed = panel.get_panel_embed()
                await interaction.response.send_message(embed=embed, view=panel)
                sent = await interaction.original_response()
                panel.panel_msg = sent
                self.outer.bot.panels[sent.id] = panel
        await interaction.response.send_modal(SearchModal(self))

    @ui.button(label="Filter: Recent", style=ButtonStyle.gray)
    async def filter_btn(self, interaction: discord.Interaction, button: ui.Button):
        # toggle mode
        self.mode = "all" if self.mode == "recent" else "recent"
        button.label = "Filter: All" if self.mode == "all" else "Filter: Recent"
        # rebuild select and update embed
        self._build_select()
        try:
            if self.selector_msg:
                await self.selector_msg.edit(embed=self.get_embed(), view=self)
            await interaction.response.defer()
        except Exception:
            pass


@bot.command()
async def moderate(ctx, member: discord.Member | None = None):
    if member is None:
        if not is_mod(ctx.author):
            await ctx.reply("You do not have permission to use moderation commands.")
            return
        view = ModerationSelectorView(ctx.author, bot, ctx.guild)
        selector_msg = await ctx.send(embed=view.get_embed(), view=view)
        view.selector_msg = selector_msg
        return
    perm_msg = require_mod(ctx.author)
    if perm_msg:
        await ctx.reply(perm_msg)
        return
    error = cannot_moderate(ctx.author, member)
    if error:
        await ctx.reply(error)
        return
    panel = ModPanel(member, ctx.author, bot)
    embed = panel.get_panel_embed()
    sent = await ctx.send(embed=embed, view=panel)
    panel.panel_msg = sent
    bot.panels[sent.id] = panel


@bot.command()
async def userinfo(ctx, member: discord.Member = None):
    member = member or ctx.author
    embed = discord.Embed(title=f"Info for {member}", color=0x546E7A)
    embed.set_thumbnail(url=getattr(member.avatar, "url", None))
    embed.add_field(name="Mention", value=member.mention, inline=True)
    embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
    embed.add_field(name="Status", value=str(member.status).title(), inline=True)
    embed.add_field(name="Roles", value=" ".join(role.mention for role in member.roles if role != member.guild.default_role), inline=False)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
    warns = get_warnings(member.id)
    warn_count = len(warns)
    embed.add_field(name="Total Warnings", value=str(warn_count), inline=True)
    actions_by_month = {}
    for record in warnings_store.get(str(member.id), []):
        ts = record["timestamp"]
        action_id = record.get("action_id", "")
        reason = record.get("reason", "")
        if "warn" in action_id.lower() or "warn" in reason.lower():
            action_type = "Warn"
        elif "amod" in action_id:
            action_type = "AutoWarn"
        elif "kick" in action_id or "kick" in reason.lower():
            action_type = "Kick"
        elif "mute" in action_id or "timeout" in reason.lower():
            action_type = "Mute"
        elif "ban" in action_id or "ban" in reason.lower():
            action_type = "Ban"
        else:
            action_type = "Other"
        try:
            timeobj = datetime.strptime(ts, "%Y-%m-%d %H:%M UTC")
            month_label = timeobj.strftime("%B %Y")
        except Exception:
            month_label = "Unknown"
        if month_label not in actions_by_month:
            actions_by_month[month_label] = {}
        actions_by_month[month_label][action_type] = actions_by_month[month_label].get(action_type, 0) + 1
    recent_month = datetime.utcnow().strftime("%B %Y")
    actions_this_month = actions_by_month.get(recent_month, {})


@bot.command()
async def roleinfo(ctx, role: discord.Role):
    member_count = sum(1 for m in ctx.guild.members if role in m.roles)
    perms = [p for p, v in role.permissions if v]
    perms_text = ", ".join(perms[:12]) + ("…" if len(perms) > 12 else "")
    color_hex = f"#{role.color.value:06x}" if role.color.value else "None"
    embed = discord.Embed(title=f"Role Info: {role.name}", color=role.color or discord.Color(0x546E7A))
    embed.add_field(name="Mention", value=role.mention, inline=True)
    embed.add_field(name="ID", value=f"`{role.id}`", inline=True)
    embed.add_field(name="Color", value=color_hex, inline=True)
    embed.add_field(name="Position", value=str(role.position), inline=True)
    embed.add_field(name="Hoisted", value=str(role.hoist), inline=True)
    embed.add_field(name="Managed", value=str(role.managed), inline=True)
    embed.add_field(name="Members", value=str(member_count), inline=True)
    embed.add_field(name="Permissions", value=perms_text or "None", inline=False)
    embed.set_footer(text=time_now())
    await ctx.send(embed=embed)


@bot.command()
async def serverinfo(ctx):
    g = ctx.guild
    text_channels = sum(1 for c in g.channels if isinstance(c, discord.TextChannel))
    voice_channels = sum(1 for c in g.channels if isinstance(c, discord.VoiceChannel))
    categories = sum(1 for c in g.channels if isinstance(c, discord.CategoryChannel))
    embed = discord.Embed(title=f"Server Info: {g.name}", color=0x546E7A)
    icon_url = getattr(g.icon, "url", None)
    if icon_url:
        embed.set_image(url=icon_url)
    embed.add_field(name="Owner", value=getattr(g.owner, "mention", "Unknown"), inline=True)
    embed.add_field(name="ID", value=f"`{g.id}`", inline=True)
    embed.add_field(name="Created", value=g.created_at.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
    embed.add_field(name="Members", value=str(g.member_count), inline=True)
    embed.add_field(name="Roles", value=str(len(g.roles)), inline=True)
    embed.add_field(name="Channels", value=f"Text: {text_channels} • Voice: {voice_channels} • Categories: {categories}", inline=False)
    await ctx.send(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    view = SetupView(ctx.author, bot)
    emb = view.get_embed()
    await ctx.send(embed=emb, view=view)

@bot.command()
@commands.has_permissions(administrator=True)
async def startautomod(ctx):
    cfg = config.setdefault(str(ctx.guild.id), {})
    cfg["automod_enabled"] = True
    save_config()
    await prefix_ack(ctx, "AutoMod enabled.")

@bot.command()
@commands.has_permissions(administrator=True)
async def stopautomod(ctx):
    cfg = config.setdefault(str(ctx.guild.id), {})
    cfg["automod_enabled"] = False
    save_config()
    await prefix_ack(ctx, "AutoMod disabled.")

@bot.command()
async def avatar(ctx, member: discord.Member = None):
    member = member or ctx.author
    url = getattr(member.display_avatar, "url", None)
    note = random.choice(FUNNY_NOTES)
    embed = discord.Embed(title=f"Avatar for {member}", description=note, color=0x8E44AD)
    if url:
        embed.set_image(url=url)
    embed.set_footer(text=time_now(), icon_url=getattr(member.avatar, "url", None))
    await ctx.send(embed=embed)
    if actions_this_month:
        summary = ", ".join([f"{k} x{v}" for k, v in actions_this_month.items()])
    else:
        summary = "No moderation actions this month"
    embed.add_field(name=f"Actions ({recent_month})", value=summary, inline=False)
    await ctx.send(embed=embed)
    await bot.log_action(ctx.guild, "UserInfo", ctx.author, member, "User info viewed", 0x3498DB)

# Slash commands
@bot.tree.command(name="moderate", description="Open moderation panel for a user")
async def moderate_slash(interaction: discord.Interaction, member: discord.Member):
    perm_msg = require_mod(interaction.user)
    if perm_msg:
        await interaction.response.send_message(perm_msg, ephemeral=True)
        return
    error = cannot_moderate(interaction.user, member)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    panel = ModPanel(member, interaction.user, bot)
    embed = panel.get_panel_embed()
    await interaction.response.send_message(embed=embed, view=panel)
    sent = await interaction.original_response()
    panel.panel_msg = sent
    bot.panels[sent.id] = panel

@bot.tree.command(name="userinfo", description="Show user info")
async def userinfo_slash(interaction: discord.Interaction, member: discord.Member | None = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"Info for {member}", color=0x546E7A)
    embed.set_thumbnail(url=getattr(member.avatar, "url", None))
    embed.add_field(name="Mention", value=member.mention, inline=True)
    embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
    embed.add_field(name="Status", value=str(member.status).title(), inline=True)
    embed.add_field(name="Roles", value=" ".join(role.mention for role in member.roles if role != member.guild.default_role), inline=False)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
    warns = get_warnings(member.id)
    warn_count = len(warns)
    embed.add_field(name="Total Warnings", value=str(warn_count), inline=True)
    await interaction.response.send_message(embed=embed)
    await bot.log_action(interaction.guild, "UserInfo", interaction.user, member, "User info viewed", 0x3498DB)

@bot.tree.command(name="avatar", description="Show a user's avatar with a funny note")
async def avatar_slash(interaction: discord.Interaction, member: discord.Member | None = None):
    member = member or interaction.user
    url = getattr(member.display_avatar, "url", None)
    note = random.choice(FUNNY_NOTES)
    embed = discord.Embed(title=f"Avatar for {member}", description=note, color=0x8E44AD)
    if url:
        embed.set_image(url=url)
    embed.set_footer(text=time_now(), icon_url=getattr(member.avatar, "url", None))
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="roleinfo", description="Show role info")
async def roleinfo_slash(interaction: discord.Interaction, role: discord.Role):
    member_count = sum(1 for m in interaction.guild.members if role in m.roles)
    perms = [p for p, v in role.permissions if v]
    perms_text = ", ".join(perms[:12]) + ("…" if len(perms) > 12 else "")
    color_hex = f"#{role.color.value:06x}" if role.color.value else "None"
    embed = discord.Embed(title=f"Role Info: {role.name}", color=role.color or discord.Color(0x546E7A))
    embed.add_field(name="Mention", value=role.mention, inline=True)
    embed.add_field(name="ID", value=f"`{role.id}`", inline=True)
    embed.add_field(name="Color", value=color_hex, inline=True)
    embed.add_field(name="Position", value=str(role.position), inline=True)
    embed.add_field(name="Hoisted", value=str(role.hoist), inline=True)
    embed.add_field(name="Managed", value=str(role.managed), inline=True)
    embed.add_field(name="Members", value=str(member_count), inline=True)
    embed.add_field(name="Permissions", value=perms_text or "None", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Show server info")
async def serverinfo_slash(interaction: discord.Interaction):
    g = interaction.guild
    text_channels = sum(1 for c in g.channels if isinstance(c, discord.TextChannel))
    voice_channels = sum(1 for c in g.channels if isinstance(c, discord.VoiceChannel))
    categories = sum(1 for c in g.channels if isinstance(c, discord.CategoryChannel))
    embed = discord.Embed(title=f"Server Info: {g.name}", color=0x546E7A)
    icon_url = getattr(g.icon, "url", None)
    if icon_url:
        embed.set_image(url=icon_url)
    embed.add_field(name="Owner", value=getattr(g.owner, "mention", "Unknown"), inline=True)
    embed.add_field(name="ID", value=f"`{g.id}`", inline=True)
    embed.add_field(name="Created", value=g.created_at.strftime("%Y-%m-%d %H:%M UTC"), inline=True)
    embed.add_field(name="Members", value=str(g.member_count), inline=True)
    embed.add_field(name="Roles", value=str(len(g.roles)), inline=True)
    embed.add_field(name="Channels", value=f"Text: {text_channels} • Voice: {voice_channels} • Categories: {categories}", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setup", description="Guided setup for roles and log channel")
async def setup_slash(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Only administrators can run setup.", ephemeral=True)
        return
    view = SetupView(interaction.user, bot)
    emb = view.get_embed()
    await interaction.response.send_message(embed=emb, view=view, ephemeral=True)

@bot.tree.command(name="startautomod", description="Enable AutoMod")
@app_commands.default_permissions(administrator=True)
async def startautomod_slash(interaction: discord.Interaction):
    cfg = config.setdefault(str(interaction.guild.id), {})
    cfg["automod_enabled"] = True
    save_config()
    await interaction.response.send_message("AutoMod enabled.", ephemeral=True)

@bot.tree.command(name="stopautomod", description="Disable AutoMod")
@app_commands.default_permissions(administrator=True)
async def stopautomod_slash(interaction: discord.Interaction):
    cfg = config.setdefault(str(interaction.guild.id), {})
    cfg["automod_enabled"] = False
    save_config()
    await interaction.response.send_message("AutoMod disabled.", ephemeral=True)

@bot.tree.command(name="setmod", description="Set moderation role")
@app_commands.default_permissions(administrator=True)
async def setmod_slash(interaction: discord.Interaction, role: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Administrator permission required.", ephemeral=True)
        return
    cfg = config.setdefault(str(interaction.guild.id), {})
    cfg["mod_role_id"] = role.id
    save_config()
    await interaction.response.send_message(f"Mod role set to {role.mention}.", ephemeral=True)
    await bot.log_action(interaction.guild, "Config Change", interaction.user, interaction.user, f"Mod role set: {role.mention}", 0x2980B9)

@bot.tree.command(name="setlog", description="Set log channel")
@app_commands.default_permissions(administrator=True)
async def setlog_slash(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Administrator permission required.", ephemeral=True)
        return
    cfg = config.setdefault(str(interaction.guild.id), {})
    cfg["log_channel_id"] = channel.id
    save_config()
    await interaction.response.send_message(f"Log channel set to {channel.mention}.", ephemeral=True)
    await bot.log_action(interaction.guild, "Config Change", interaction.user, interaction.user, f"Log channel set: {channel.mention}", 0x2980B9)

@bot.tree.command(name="setmodbypass", description="Set AutoMod bypass role")
@app_commands.default_permissions(administrator=True)
async def setmodbypass_slash(interaction: discord.Interaction, role: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("Administrator permission required.", ephemeral=True)
        return
    cfg = config.setdefault(str(interaction.guild.id), {})
    cfg["bypass_role_id"] = role.id
    save_config()
    await interaction.response.send_message(f"Bypass role set to {role.mention}.", ephemeral=True)
    await bot.log_action(interaction.guild, "Config Change", interaction.user, interaction.user, f"Bypass role set: {role.mention}", 0x2980B9)

@bot.tree.command(name="purge", description="Delete recent messages")
@app_commands.checks.has_permissions(manage_messages=True)
async def purge_slash(interaction: discord.Interaction, amount: int):
    if amount < 1 or amount > 100:
        await interaction.response.send_message("Amount must be 1 to 100.", ephemeral=True)
        return
    snapshot = []
    async for m in interaction.channel.history(limit=amount):
        files = []
        for att in m.attachments[:3]:
            try:
                files.append(await att.to_file())
            except Exception:
                pass
        snapshot.append({"message": m, "files": files})
    await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(f"Purged {amount} messages.", ephemeral=True)
    notice_embed = discord.Embed(title="Purge Completed", description=f"{interaction.user.mention} purged `{amount}` messages in {interaction.channel.mention}.", color=0xE67E22, timestamp=datetime.utcnow())
    temp = await interaction.channel.send(embed=notice_embed)
    asyncio.create_task(_delete_later(temp, 3))
    await bot.log_action(interaction.guild, "Purge", interaction.user, interaction.user, f"Purged {amount} messages in {interaction.channel.mention}", 0xE67E22)
    await log_purged_messages(interaction.guild, interaction.user, interaction.channel, snapshot)

@bot.tree.command(name="warn", description="Warn a user")
async def warn_slash(interaction: discord.Interaction, member: discord.Member, reason: str):
    perm_msg = require_mod(interaction.user)
    if perm_msg:
        await interaction.response.send_message(perm_msg, ephemeral=True)
        return
    error = cannot_moderate(interaction.user, member)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    ensure_list(str(member.id))
    warnings_store[str(member.id)].append({
        "reason": reason,
        "moderator_id": interaction.user.id,
        "timestamp": time_now(),
        "action_id": f"warn-{datetime.utcnow().timestamp()}"
    })
    save_warnings()
    warn_count = len(get_warnings(member.id))
    if warn_count == 3:
        await auto_timeout(member, interaction, 15, "Reached 3 warnings: auto timeout")
    elif warn_count == 5:
        await auto_timeout(member, interaction, 60*24, "Reached 5 warnings: auto timeout")
    await interaction.response.send_message(f"{member.mention} warned.", ephemeral=True)
    msg = await bot.log_action(interaction.guild, "Warn", interaction.user, member, reason, 0xF1C40F, extra_footer=f"Warning issued on: {time_now()} | Active Warnings: {warn_count}")
    if msg:
        bot.bg_tasks[msg.id] = {"message": msg, "action": "warn", "user_id": member.id, "timestamp": time_now(), "mod_name": interaction.user.name, "mod_icon_url": getattr(interaction.user.avatar, "url", None)}

@bot.tree.command(name="kick", description="Kick a user")
async def kick_slash(interaction: discord.Interaction, member: discord.Member, reason: str):
    perm_msg = require_mod(interaction.user)
    if perm_msg:
        await interaction.response.send_message(perm_msg, ephemeral=True)
        return
    error = cannot_moderate(interaction.user, member)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"{member.mention} kicked.", ephemeral=True)
        await bot.log_action(interaction.guild, "Kick", interaction.user, member, reason, 0xE74C3C)
    except Exception:
        await interaction.response.send_message("Failed to kick user.", ephemeral=True)

@bot.tree.command(name="ban", description="Ban a user for a duration")
async def ban_slash(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str):
    perm_msg = require_mod(interaction.user)
    if perm_msg:
        await interaction.response.send_message(perm_msg, ephemeral=True)
        return
    error = cannot_moderate(interaction.user, member)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    dur = parse_duration_arg(duration)
    if dur is None:
        await interaction.response.send_message("Invalid duration. Use forms like 2d, 5h, or 1d2h.", ephemeral=True)
        return
    try:
        try:
            dm = ack_embed(interaction.user, f"You have been banned from {interaction.guild.name} for {duration}. Reason: {reason}")
            await member.send(embed=dm)
        except Exception:
            pass
        await member.ban(reason=reason)
        preview = bot._log_embed("Ban", interaction.user, member, reason, 0x2C3E50, duration=duration)
        await slash_ephemeral_ack(interaction, preview)
        msg = await bot.log_action(interaction.guild, "Ban", interaction.user, member, reason, 0x2C3E50, duration=duration, extra_footer="Action Expires In: updating...")
        bot.bg_tasks[msg.id] = {"message": msg, "ends": datetime.utcnow()+dur, "action": "ban", "mod_name": interaction.user.name, "mod_icon_url": getattr(interaction.user.avatar, "url", None)}
    except Exception:
        await interaction.response.send_message("Failed to ban user.", ephemeral=True)

@bot.tree.command(name="unban", description="Unban a user")
async def unban_slash(interaction: discord.Interaction, user: discord.User):
    perm_msg = require_mod(interaction.user)
    if perm_msg:
        await interaction.response.send_message(perm_msg, ephemeral=True)
        return
    try:
        await interaction.guild.unban(user, reason=f"Unbanned by {interaction.user}")
        await interaction.response.send_message(f"{user} unbanned.", ephemeral=True)
        await bot.log_action(interaction.guild, "Unban", interaction.user, user, "Unbanned", 0x27AE60)
    except Exception:
        await interaction.response.send_message("User not found in ban list.", ephemeral=True)

@bot.tree.command(name="mute", description="Timeout a user for a duration")
async def mute_slash(interaction: discord.Interaction, member: discord.Member, duration: str, reason: str):
    perm_msg = require_mod(interaction.user)
    if perm_msg:
        await interaction.response.send_message(perm_msg, ephemeral=True)
        return
    error = cannot_moderate(interaction.user, member)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    dur = parse_duration_arg(duration)
    if dur is None:
        await interaction.response.send_message("Invalid duration. Use forms like 2d, 5h, or 1d2h.", ephemeral=True)
        return
    until = datetime.utcnow() + dur
    soft_mutes[member.id] = until
    try:
        dm = ack_embed(interaction.user, f"You have been muted in {interaction.guild.name} for {duration}. Reason: {reason}")
        await member.send(embed=dm)
    except Exception:
        pass
    preview = bot._log_embed("Timeout (Mute)", interaction.user, member, reason, 0x3498DB, duration=duration)
    await slash_ephemeral_ack(interaction, preview)
    msg = await bot.log_action(interaction.guild, "Timeout (Mute)", interaction.user, member, reason, 0x3498DB, duration=duration, extra_footer="Action Expires In: updating...")
    bot.bg_tasks[msg.id] = {"message": msg, "ends": until, "action": "timeout", "mod_name": interaction.user.name, "mod_icon_url": getattr(interaction.user.avatar, "url", None)}

@bot.tree.command(name="unmute", description="Remove a user's timeout")
async def unmute_slash(interaction: discord.Interaction, member: discord.Member):
    perm_msg = require_mod(interaction.user)
    if perm_msg:
        await interaction.response.send_message(perm_msg, ephemeral=True)
        return
    soft_mutes.pop(member.id, None)
    preview = bot._log_embed("Unmute", interaction.user, member, "Timeout removed", 0x8E44AD)
    await slash_ephemeral_ack(interaction, preview)
    await bot.log_action(interaction.guild, "Unmute", interaction.user, member, "Timeout removed", 0x8E44AD)

@bot.tree.command(name="addrole", description="Add a role to a user")
async def addrole_slash(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    perm_msg = require_mod(interaction.user)
    if perm_msg:
        await interaction.response.send_message(perm_msg, ephemeral=True)
        return
    error = cannot_moderate(interaction.user, member)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    try:
        await member.add_roles(role, reason=f"Added via slash by {interaction.user}")
        preview = bot._log_embed("Add Role", interaction.user, member, f"Added role {role.mention}", 0x8E44AD)
        await slash_ephemeral_ack(interaction, preview)
        await bot.log_action(interaction.guild, "Add Role", interaction.user, member, f"Added role {role.mention}", 0x8E44AD)
    except Exception:
        await interaction.response.send_message("Failed to add role.", ephemeral=True)

@bot.tree.command(name="removerole", description="Remove a role from a user")
async def removerole_slash(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    perm_msg = require_mod(interaction.user)
    if perm_msg:
        await interaction.response.send_message(perm_msg, ephemeral=True)
        return
    error = cannot_moderate(interaction.user, member)
    if error:
        await interaction.response.send_message(error, ephemeral=True)
        return
    try:
        await member.remove_roles(role, reason=f"Removed via slash by {interaction.user}")
        preview = bot._log_embed("Remove Role", interaction.user, member, f"Removed role {role.mention}", 0x8E44AD)
        await slash_ephemeral_ack(interaction, preview)
        await bot.log_action(interaction.guild, "Remove Role", interaction.user, member, f"Removed role {role.mention}", 0x8E44AD)
    except Exception:
        await interaction.response.send_message("Failed to remove role.", ephemeral=True)
 

@bot.tree.command(name="help", description="Show command help")
async def help_slash(interaction: discord.Interaction):
    embed = build_help_embed(interaction.user, interaction.guild)
    await interaction.response.send_message(embed=embed, ephemeral=True)

 

@bot.command()
async def help(ctx):
    embed = build_help_embed(ctx.author, ctx.guild)
    await ctx.send(embed=embed)


@bot.command()
@commands.has_permissions(administrator=True)
async def setmod(ctx, role: discord.Role):
    cfg = config.setdefault(str(ctx.guild.id), {})
    cfg["mod_role_id"] = role.id
    save_config()
    await ctx.reply(f"Mod role set to {role.mention}.", mention_author=False)
    await bot.log_action(ctx.guild, "Config Change", ctx.author, ctx.author, f"Mod role set: {role.mention}", 0x2980B9)


@bot.command()
@commands.has_permissions(administrator=True)
async def setlog(ctx, channel: discord.TextChannel):
    cfg = config.setdefault(str(ctx.guild.id), {})
    cfg["log_channel_id"] = channel.id
    save_config()
    await ctx.reply(f"Log channel set to {channel.mention}.", mention_author=False)
    await bot.log_action(ctx.guild, "Config Change", ctx.author, ctx.author, f"Log channel set: {channel.mention}", 0x2980B9)


@bot.command()
@commands.has_permissions(administrator=True)
async def setmodbypass(ctx, role: discord.Role):
    cfg = config.setdefault(str(ctx.guild.id), {})
    cfg["bypass_role_id"] = role.id
    save_config()
    await ctx.reply(f"Bypass role set to {role.mention}.", mention_author=False)
    await bot.log_action(ctx.guild, "Config Change", ctx.author, ctx.author, f"Bypass role set: {role.mention}", 0x2980B9)


@bot.command()
@commands.has_permissions(manage_messages=True)
async def purge(ctx, amount: int):
    if amount < 1 or amount > 100:
        await ctx.reply("Amount must be 1 to 100.")
        return
    snapshot = []
    async for m in ctx.channel.history(limit=amount):
        files = []
        for att in m.attachments[:3]:
            try:
                files.append(await att.to_file())
            except Exception:
                pass
        snapshot.append({"message": m, "files": files})
    await ctx.channel.purge(limit=amount+1)
    notice_embed = discord.Embed(title="Purge Completed", description=f"{ctx.author.mention} purged `{amount}` messages in {ctx.channel.mention}.", color=0xE67E22, timestamp=datetime.utcnow())
    notice = await ctx.send(embed=notice_embed)
    asyncio.create_task(_delete_later(notice, 3))
    await bot.log_action(ctx.guild, "Purge", ctx.author, ctx.author, f"Purged {amount} messages in {ctx.channel.mention}", 0xE67E22)
    await log_purged_messages(ctx.guild, ctx.author, ctx.channel, snapshot)


@bot.command()
async def warn(ctx, member: discord.Member, *, reason: str):
    perm_msg = require_mod(ctx.author)
    if perm_msg:
        await prefix_ack(ctx, perm_msg)
        return
    error = cannot_moderate(ctx.author, member)
    if error:
        await prefix_ack(ctx, error)
        return
    ensure_list(str(member.id))
    warnings_store[str(member.id)].append({
        "reason": reason,
        "moderator_id": ctx.author.id,
        "timestamp": time_now(),
        "action_id": f"warn-{datetime.utcnow().timestamp()}"
    })
    save_warnings()
    warn_count = len(get_warnings(member.id))
    if warn_count == 3:
        await auto_timeout(member, ctx, 15, "Reached 3 warnings: auto timeout")
    elif warn_count == 5:
        await auto_timeout(member, ctx, 60*24, "Reached 5 warnings: auto timeout")
    await prefix_ack(ctx, f"{member.mention} warned.")
    msg = await bot.log_action(ctx.guild, "Warn", ctx.author, member, reason, 0xF1C40F, extra_footer=f"Warning issued on: {time_now()} | Active Warnings: {warn_count}")
    if msg:
        bot.bg_tasks[msg.id] = {"message": msg, "action": "warn", "user_id": member.id, "timestamp": time_now(), "mod_name": ctx.author.name, "mod_icon_url": getattr(ctx.author.avatar, "url", None)}


@bot.command()
async def kick(ctx, member: discord.Member, *, reason: str):
    perm_msg = require_mod(ctx.author)
    if perm_msg:
        await prefix_ack(ctx, perm_msg)
        return
    error = cannot_moderate(ctx.author, member)
    if error:
        await prefix_ack(ctx, error)
        return
    try:
        await member.kick(reason=reason)
        preview = bot._log_embed("Kick", ctx.author, member, reason, 0x2C3E50)
        msg = await ctx.send(embed=preview)
        asyncio.create_task(_delete_later(msg, 5))
        await bot.log_action(ctx.guild, "Kick", ctx.author, member, reason, 0x2C3E50)
    except Exception:
        await prefix_ack(ctx, "Failed to kick user.")


@bot.command()
async def ban(ctx, member: discord.Member, duration: str, *, reason: str):
    perm_msg = require_mod(ctx.author)
    if perm_msg:
        await prefix_ack(ctx, perm_msg)
        return
    error = cannot_moderate(ctx.author, member)
    if error:
        await prefix_ack(ctx, error)
        return
    dur = parse_duration_arg(duration)
    if dur is None:
        await prefix_ack(ctx, "Invalid duration. Use forms like 2d, 5h, or 1d2h.")
        return
    try:
        try:
            dm = ack_embed(ctx.author, f"You have been banned from {ctx.guild.name} for {duration}. Reason: {reason}")
            await member.send(embed=dm)
        except Exception:
            pass
        await member.ban(reason=reason)
        preview = bot._log_embed("Ban", ctx.author, member, reason, 0x2C3E50, duration=duration)
        msg_preview = await ctx.send(embed=preview)
        asyncio.create_task(_delete_later(msg_preview, 5))
        msg = await bot.log_action(ctx.guild, "Ban", ctx.author, member, reason, 0x2C3E50, duration=duration, extra_footer="Action Expires In: updating...")
        bot.bg_tasks[msg.id] = {"message": msg, "ends": datetime.utcnow()+dur, "action": "ban", "mod_name": ctx.author.name, "mod_icon_url": getattr(ctx.author.avatar, "url", None)}
    except Exception:
        await prefix_ack(ctx, "Failed to ban user.")


@bot.command()
async def unban(ctx, *, query: str):
    perm_msg = require_mod(ctx.author)
    if perm_msg:
        await prefix_ack(ctx, perm_msg)
        return
    bans = await ctx.guild.bans()
    target = None
    if query.isdigit():
        target = next((e.user for e in bans if e.user.id == int(query)), None)
    if not target:
        lower = query.lower()
        target = next((e.user for e in bans if lower in str(e.user).lower()), None)
    if target:
        await ctx.guild.unban(target, reason=f"Unbanned by {ctx.author}")
        await prefix_ack(ctx, f"{target} unbanned.")
        await bot.log_action(ctx.guild, "Unban", ctx.author, target, "Unbanned", 0x27AE60)
    else:
        await prefix_ack(ctx, "User not found in ban list.")


@bot.command()
async def mute(ctx, member: discord.Member, duration: str, *, reason: str):
    perm_msg = require_mod(ctx.author)
    if perm_msg:
        await prefix_ack(ctx, perm_msg)
        return
    error = cannot_moderate(ctx.author, member)
    if error:
        await prefix_ack(ctx, error)
        return
    dur = parse_duration_arg(duration)
    if dur is None:
        await prefix_ack(ctx, "Invalid duration. Use forms like 2d, 5h, or 1d2h.")
        return
    until = datetime.utcnow() + dur
    soft_mutes[member.id] = until
    try:
        dm = ack_embed(ctx.author, f"You have been muted in {ctx.guild.name} for {duration}. Reason: {reason}")
        await member.send(embed=dm)
    except Exception:
        pass
    preview = bot._log_embed("Timeout (Mute)", ctx.author, member, reason, 0x3498DB, duration=duration)
    msg_preview = await ctx.send(embed=preview)
    asyncio.create_task(_delete_later(msg_preview, 5))
    msg = await bot.log_action(ctx.guild, "Timeout (Mute)", ctx.author, member, reason, 0x3498DB, duration=duration, extra_footer="Action Expires In: updating...")
    bot.bg_tasks[msg.id] = {"message": msg, "ends": until, "action": "timeout", "mod_name": ctx.author.name, "mod_icon_url": getattr(ctx.author.avatar, "url", None)}


@bot.command()
async def unmute(ctx, member: discord.Member):
    perm_msg = require_mod(ctx.author)
    if perm_msg:
        await prefix_ack(ctx, perm_msg)
        return
    soft_mutes.pop(member.id, None)
    preview = bot._log_embed("Unmute", ctx.author, member, "Timeout removed", 0x8E44AD)
    msg_preview = await ctx.send(embed=preview)
    asyncio.create_task(_delete_later(msg_preview, 5))
    await bot.log_action(ctx.guild, "Unmute", ctx.author, member, "Timeout removed", 0x8E44AD)


@bot.command()
async def addrole(ctx, member: discord.Member, role: discord.Role):
    perm_msg = require_mod(ctx.author)
    if perm_msg:
        await prefix_ack(ctx, perm_msg)
        return
    error = cannot_moderate(ctx.author, member)
    if error:
        await prefix_ack(ctx, error)
        return
    try:
        await member.add_roles(role, reason=f"Added via command by {ctx.author}")
        preview = bot._log_embed("Add Role", ctx.author, member, f"Added role {role.mention}", 0x8E44AD)
        msg_preview = await ctx.send(embed=preview)
        asyncio.create_task(_delete_later(msg_preview, 5))
        await bot.log_action(ctx.guild, "Add Role", ctx.author, member, f"Added role {role.mention}", 0x8E44AD)
    except Exception:
        await prefix_ack(ctx, "Failed to add role.")


@bot.command()
async def removerole(ctx, member: discord.Member, role: discord.Role):
    perm_msg = require_mod(ctx.author)
    if perm_msg:
        await prefix_ack(ctx, perm_msg)
        return
    error = cannot_moderate(ctx.author, member)
    if error:
        await prefix_ack(ctx, error)
        return
    try:
        await member.remove_roles(role, reason=f"Removed via command by {ctx.author}")
        preview = bot._log_embed("Remove Role", ctx.author, member, f"Removed role {role.mention}", 0x8E44AD)
        msg_preview = await ctx.send(embed=preview)
        asyncio.create_task(_delete_later(msg_preview, 5))
        await bot.log_action(ctx.guild, "Remove Role", ctx.author, member, f"Removed role {role.mention}", 0x8E44AD)
    except Exception:
        await prefix_ack(ctx, "Failed to remove role.")


@tasks.loop(seconds=1)
async def update_panel_timers(botinstance):
    to_delete = []
    for msg_id, panel in list(botinstance.panels.items()):
        if panel.panel_msg:
            embed = panel.get_panel_embed()
            try:
                await panel.panel_msg.edit(embed=embed)
            except Exception:
                to_delete.append(msg_id)
        else:
            to_delete.append(msg_id)
        if panel.expiry < datetime.utcnow():
            if panel.panel_msg:
                try:
                    await panel.panel_msg.delete()
                except Exception:
                    pass
            to_delete.append(msg_id)
    for msg_id in to_delete:
        botinstance.panels.pop(msg_id, None)


@tasks.loop(seconds=30)
async def update_log_footers(botinstance):
    now = datetime.utcnow()
    for msg_id, data in list(botinstance.bg_tasks.items()):
        msg = data["message"]
        action = data.get("action")
        embed = msg.embeds[0]
        mod_name = data.get("mod_name")
        mod_icon = data.get("mod_icon_url")
        if action == "warn":
            user_id = data.get("user_id")
            ts = data.get("timestamp", time_now())
            count = len(get_warnings(int(user_id))) if user_id else 0
            status = f"Warning issued on: {ts} | Active Warnings: {count}"
        else:
            ends = data["ends"]
            left = ends - now
            if left.total_seconds() <= 0:
                status = "Action expired."
                botinstance.bg_tasks.pop(msg_id)
            else:
                mins_total = int(left.total_seconds() // 60)
                status = f"Action Expires In: {mins_total} minutes"
        footer_text = status
        embed.set_footer(text=footer_text, icon_url=mod_icon)
        try:
            await msg.edit(embed=embed)
        except Exception:
            botinstance.bg_tasks.pop(msg_id, None)


async def _delete_later(msg, seconds=5):
    try:
        await asyncio.sleep(seconds)
        await msg.delete()
    except Exception:
        pass

async def log_purged_messages(guild, moderator, channel, snapshot):
    log_channel = get_log_channel(guild)
    if not log_channel:
        return
    count = len(snapshot)
    if count >= 15:
        try:
            buf = io.StringIO()
            buf.write(f"Purge in {channel} by {moderator} at {time_now()}\n")
            for entry in snapshot:
                m = entry.get("message")
                content = m.content if m.content else "(no content)"
                buf.write(f"[{m.created_at.strftime('%Y-%m-%d %H:%M UTC')}] {m.author} ({m.author.id}): {content}\n")
            buf.seek(0)
            report = bot._log_embed(
                action="Purge Report",
                moderator=moderator,
                target=moderator,
                reason=f"Channel: {channel.mention}",
                color=0xE67E22,
                extra_footer=f"Items: {count}"
            )
            report.add_field(name="Details", value="Full message list attached as a text report.", inline=False)
            await log_channel.send(embed=report, file=discord.File(buf, filename=f"purge_{channel.id}_{int(datetime.utcnow().timestamp())}.txt"))
        except Exception:
            pass
    else:
        lines = []
        attach_files = []
        for entry in snapshot:
            m = entry.get("message")
            content = m.content if m.content else "(no content)"
            trunc = (content[:160] + "…") if len(content) > 160 else content
            stamp = m.created_at.strftime("%H:%M")
            lines.append(f"• {m.author.mention} [{stamp}] — {trunc}")
            for f in entry.get("files", []):
                if len(attach_files) < 10:
                    attach_files.append(f)
        try:
            report = bot._log_embed(
                action="Purge Report",
                moderator=moderator,
                target=moderator,
                reason=f"Channel: {channel.mention}",
                color=0xE67E22,
                extra_footer=f"Items: {count}"
            )
            if lines:
                visible = lines[:10]
                if count > 10:
                    visible.append(f"…and {count - 10} more")
                report.add_field(name="Messages", value="\n".join(visible), inline=False)
            if attach_files:
                report.add_field(name="Attachments", value=f"Re-uploaded: {len(attach_files)} (max 10)", inline=False)
                await log_channel.send(embed=report, files=attach_files)
            else:
                await log_channel.send(embed=report)
        except Exception:
            pass

async def prefix_ack(ctx, text):
    try:
        emb = ack_embed(ctx.author, text)
        msg = await ctx.reply(embed=emb, mention_author=False)
        asyncio.create_task(_delete_later(msg, 5))
    except Exception:
        try:
            emb = ack_embed(ctx.author, text)
            msg = await ctx.send(embed=emb)
            asyncio.create_task(_delete_later(msg, 5))
        except Exception:
            pass

def ack_embed(actor, text):
    low = text.lower()
    if any(k in low for k in ["failed", "invalid", "permission", "not found", "cannot"]):
        color = 0x2C3E50
        title = "Action Failed"
    elif any(k in low for k in ["added", "removed", "warned", "kicked", "banned", "muted", "unmuted", "set", "saved", "enabled", "disabled"]):
        color = 0x8E44AD
        title = "Action Completed"
    else:
        color = 0x3498DB
        title = "Notice"
    embed = discord.Embed(title=title, description=text, color=color, timestamp=datetime.utcnow())
    embed.set_author(name=f"{getattr(actor, 'name', str(actor))}", icon_url=getattr(getattr(actor, 'avatar', None), 'url', None))
    embed.set_footer(text=time_now(), icon_url=getattr(getattr(actor, 'avatar', None), 'url', None))
    return embed

async def _delete_later(message_obj, seconds):
    try:
        await asyncio.sleep(seconds)
        await message_obj.delete()
    except Exception:
        pass

async def _delete_ephemeral(interaction, seconds):
    try:
        await asyncio.sleep(seconds)
        await interaction.delete_original_response()
    except Exception:
        pass

async def slash_ephemeral_ack(interaction, embed):
    await interaction.response.send_message(embed=embed, ephemeral=True)
    asyncio.create_task(_delete_ephemeral(interaction, 5))

async def slash_ephemeral_text(interaction, content):
    await interaction.response.send_message(content, ephemeral=True)
    asyncio.create_task(_delete_ephemeral(interaction, 5))
class SetupView(ui.View):
    def __init__(self, issuer: discord.Member, bot: commands.Bot):
        super().__init__(timeout=300)
        self.issuer = issuer
        self.bot = bot
        self.page = 1
        self.automod_enabled = config.setdefault(str(issuer.guild.id), {}).get("automod_enabled", True)
        self.selected_mod_role: discord.Role | None = get_mod_role(issuer.guild)
        self.selected_bypass_role: discord.Role | None = get_mod_bypass_role(issuer.guild)
        self.selected_log_channel: discord.TextChannel | None = get_log_channel(issuer.guild)
        self._build_page_items()

    def _build_page_items(self):
        for item in list(self.children):
            self.remove_item(item)
        roles = [r for r in self.issuer.guild.roles if r != self.issuer.guild.default_role]
        roles_sorted = sorted(roles, key=lambda r: r.position, reverse=True)[:25]
        channels = [c for c in self.issuer.guild.channels if isinstance(c, discord.TextChannel)]
        chan_sorted = sorted(channels, key=lambda c: c.position)[:25]

        if self.page == 1:
            mod_select = ui.Select(placeholder="Page 1/4: Select Mod Role", min_values=1, max_values=1)
            for r in roles_sorted:
                mod_select.add_option(label=r.name, value=str(r.id))
            async def on_mod_select(interaction: discord.Interaction):
                rid = int(mod_select.values[0])
                self.selected_mod_role = interaction.guild.get_role(rid)
                await slash_ephemeral_text(interaction, f"Mod role set to {self.selected_mod_role.mention}.")
            mod_select.callback = on_mod_select
            self.add_item(mod_select)
        elif self.page == 2:
            bypass_select = ui.Select(placeholder="Page 2/4: Select Bypass Role (optional)", min_values=0, max_values=1)
            bypass_select.add_option(label="None", value="none")
            for r in roles_sorted:
                bypass_select.add_option(label=r.name, value=str(r.id))
            async def on_bypass_select(interaction: discord.Interaction):
                val = bypass_select.values[0]
                self.selected_bypass_role = None if val == "none" else interaction.guild.get_role(int(val))
                msg = "Bypass role cleared." if self.selected_bypass_role is None else f"Bypass role set to {self.selected_bypass_role.mention}."
                await slash_ephemeral_text(interaction, msg)
            bypass_select.callback = on_bypass_select
            self.add_item(bypass_select)
        elif self.page == 3:
            chan_select = ui.Select(placeholder="Page 3/4: Select Log Channel", min_values=1, max_values=1)
            for c in chan_sorted:
                chan_select.add_option(label=f"#{c.name}", value=str(c.id))
            async def on_chan_select(interaction: discord.Interaction):
                cid = int(chan_select.values[0])
                self.selected_log_channel = interaction.guild.get_channel(cid)
                await slash_ephemeral_text(interaction, f"Log channel set to {self.selected_log_channel.mention}.")
            chan_select.callback = on_chan_select
            self.add_item(chan_select)
        else:
            enable_btn = ui.Button(label="Enable AutoMod", style=discord.ButtonStyle.green)
            disable_btn = ui.Button(label="Disable AutoMod", style=discord.ButtonStyle.red)
            async def on_enable(interaction: discord.Interaction):
                self.automod_enabled = True
                await slash_ephemeral_text(interaction, "AutoMod enabled.")
            async def on_disable(interaction: discord.Interaction):
                self.automod_enabled = False
                await slash_ephemeral_text(interaction, "AutoMod disabled.")
            enable_btn.callback = on_enable
            disable_btn.callback = on_disable
            self.add_item(enable_btn)
            self.add_item(disable_btn)

        prev_btn = ui.Button(label="Back", style=discord.ButtonStyle.gray, disabled=self.page == 1)
        next_btn = ui.Button(label="Next", style=discord.ButtonStyle.blurple, disabled=self.page == 4)
        async def on_prev(interaction: discord.Interaction):
            self.page = max(1, self.page - 1)
            self._build_page_items()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        async def on_next(interaction: discord.Interaction):
            self.page = min(4, self.page + 1)
            self._build_page_items()
            await interaction.response.edit_message(embed=self.get_embed(), view=self)
        prev_btn.callback = on_prev
        next_btn.callback = on_next
        self.add_item(prev_btn)
        self.add_item(next_btn)

    def get_embed(self):
        desc = [
            f"Setup (Page {self.page}/4)",
            f"Mod Role: {self.selected_mod_role.mention if self.selected_mod_role else '`not set`'}",
            f"Bypass Role: {self.selected_bypass_role.mention if self.selected_bypass_role else '`none`'}",
            f"Log Channel: {self.selected_log_channel.mention if self.selected_log_channel else '`not set`'}",
            f"AutoMod: {'enabled' if self.automod_enabled else 'disabled'}",
            "Configure this page, use Next/Back to navigate, then Save.",
        ]
        embed = discord.Embed(title="Setup Panel", description="\n".join(desc), color=0x8E44AD)
        banner = getattr(self.issuer.guild, "banner", None)
        banner_url = getattr(banner, "url", None)
        icon_url = getattr(self.issuer.guild.icon, "url", None)
        if banner_url:
            embed.set_image(url=banner_url)
        elif icon_url:
            embed.set_image(url=icon_url)
        embed.set_footer(text=time_now())
        return embed

    @ui.button(label="Save", style=discord.ButtonStyle.green)
    async def save_btn(self, interaction: discord.Interaction, button: ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only admins can run setup.", ephemeral=True)
            return
        conf = config.setdefault(str(interaction.guild.id), {})
        if self.selected_mod_role:
            conf["mod_role_id"] = self.selected_mod_role.id
        if self.selected_bypass_role is not None:
            conf["mod_bypass_role_id"] = self.selected_bypass_role.id if self.selected_bypass_role else None
        if self.selected_log_channel:
            conf["log_channel_id"] = self.selected_log_channel.id
        conf["automod_enabled"] = bool(self.automod_enabled)
        save_config()
        await interaction.response.send_message(embed=ack_embed(interaction.user, "Configuration saved."), ephemeral=True)
        await self.bot.log_action(interaction.guild, "Setup Saved", interaction.user, interaction.user, "Bot configuration updated via Setup panel.", 0x2ECC71)
        
bot.run("token")
