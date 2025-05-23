import logging
import time
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define roles
ADMIN = "ADMIN"
MODERATOR = "MODERATOR"
USER = "USER"

# Store user roles (in-memory)
user_roles = {}  # {chat_id: {user_id: role}}
muted_users = {} # {chat_id: {user_id: mute_end_time}}

# Hardcoded bot owner ID (replace with your actual Telegram User ID)
BOT_OWNER_ID = 123456789  # Example ID

# --- Spam Protection Configuration ---
spam_protection_enabled = True
MAX_MESSAGES_PER_WINDOW = 5
RATE_LIMIT_WINDOW_SECONDS = 10
SPAM_MUTE_DURATION_SECONDS = 300 # 5 minutes
message_timestamps = {} # {chat_id: {user_id: [timestamp1, ...]}}
forbidden_keywords = ["keyword1", "spamlink.com", "another_bad_word"] # Case-insensitive

# --- Reporting System Data Structure ---
user_reports = {} # {chat_id: {reported_user_id: [{'reporter_id': user_id, 'reason': text, 'timestamp': datetime}]}}

# --- Configuration for Auto-Actions on Reports ---
REPORT_THRESHOLD_MUTE = 3
REPORT_THRESHOLD_KICK = 5
AUTO_MUTE_DURATION_ON_REPORTS = "2h" # format for parse_duration
enable_auto_actions_on_reports = True


# Helper functions
def get_user_role(chat_id: int, user_id: int) -> str:
    """Returns the role of the user. Defaults to USER."""
    return user_roles.get(chat_id, {}).get(user_id, USER)

def is_admin(chat_id: int, user_id: int) -> bool:
    """Returns True if the user is an ADMIN."""
    return get_user_role(chat_id, user_id) == ADMIN

def is_moderator(chat_id: int, user_id: int) -> bool:
    """Returns True if the user is a MODERATOR or ADMIN."""
    return get_user_role(chat_id, user_id) in [ADMIN, MODERATOR]

# Define a command handler. These usually take the two arguments update and
# context.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message when the command /start is issued."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    # Initialize BOT_OWNER_ID as ADMIN on first /start
    if user_id == BOT_OWNER_ID and chat_id not in user_roles:
        user_roles[chat_id] = {BOT_OWNER_ID: ADMIN}
        logger.info(f"Bot owner {BOT_OWNER_ID} initialized as ADMIN in chat {chat_id}.")
    elif user_id == BOT_OWNER_ID and user_roles.get(chat_id, {}).get(BOT_OWNER_ID) != ADMIN :
        if chat_id not in user_roles:
            user_roles[chat_id] = {}
        user_roles[chat_id][BOT_OWNER_ID] = ADMIN
        logger.info(f"Bot owner {BOT_OWNER_ID} re-initialized as ADMIN in chat {chat_id}.")


    role = get_user_role(chat_id, user_id)
    await update.message.reply_text(f"Hello! Your role is: {role}")

async def set_role_command(update: Update, context: ContextTypes.DEFAULT_TYPE, role_to_set: str) -> None:
    """Generic function to set a user's role."""
    setter_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not is_admin(chat_id, setter_id) and role_to_set in [ADMIN, MODERATOR]: # Only admin can set ADMIN or MODERATOR
        if not (setter_id == BOT_OWNER_ID and role_to_set == ADMIN): # Bot owner can always set ADMIN
             await update.message.reply_text("You are not authorized to set this role.")
             return
    elif not is_admin(chat_id, setter_id) and role_to_set == USER : # Admin can remove any role
        await update.message.reply_text("You are not authorized to remove permissions.")
        return


    try:
        # Extract username from the command
        username_to_set = context.args[0]
        if username_to_set.startswith('@'):
            username_to_set = username_to_set[1:]
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /<command> @username")
        return

    target_user_id = None
    target_username = "User" # Default username
    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username or update.message.reply_to_message.from_user.first_name
    elif update.message.entities:
        for entity, text in update.message.parse_entities().items():
            if entity.type == 'mention' and text.lstrip('@') == username_to_set :
                 # This is still not a reliable way to get user_id directly from @username mention
                 # We'll rely on text_mention or providing user_id for now
                 pass
            elif entity.type == 'text_mention': # User mentioned by name (linked)
                target_user_id = entity.user.id
                target_username = entity.user.username or entity.user.first_name
                break
    
    if not target_user_id and username_to_set:
        try:
            target_user_id = int(username_to_set) # Try if username_to_set is actually an ID
            # Try to get username if possible
            try:
                member = await context.bot.get_chat_member(chat_id, target_user_id)
                target_username = member.user.username or member.user.first_name or f"User (ID: {target_user_id})"
            except Exception:
                target_username = f"User (ID: {target_user_id})"

        except ValueError:
            await update.message.reply_text(
                f"Could not find user {username_to_set}. "
                "Please reply to the user's message, use a linked @mention, or provide their User ID."
            )
            return

    if not target_user_id:
        await update.message.reply_text(
            "Please reply to a user's message or mention them with @username/user_id to set their role."
        )
        return

    if chat_id not in user_roles:
        user_roles[chat_id] = {}

    if target_user_id == BOT_OWNER_ID and setter_id != BOT_OWNER_ID:
        await update.message.reply_text(f"Cannot change the role of the bot owner.")
        return

    user_roles[chat_id][target_user_id] = role_to_set
    logger.info(f"User {target_user_id} in chat {chat_id} role set to {role_to_set} by {setter_id}.")
    await update.message.reply_text(f"User @{target_username} (ID: {target_user_id}) role set to {role_to_set}.")

# --- Mute/Unmute Functionality ---

def parse_duration(duration_str: str) -> timedelta | None:
    """Parses a duration string (e.g., '1h', '30m', '1d') into a timedelta."""
    if not duration_str or len(duration_str) < 2:
        return None
    value_str = duration_str[:-1]
    unit = duration_str[-1].lower()
    if not value_str.isdigit():
        return None
    value = int(value_str)
    
    if unit == 'm':
        return timedelta(minutes=value)
    elif unit == 'h':
        return timedelta(hours=value)
    elif unit == 'd':
        return timedelta(days=value)
    return None

async def mute_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mutes a user for a specified duration."""
    muter_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not is_moderator(chat_id, muter_id): # MODERATOR or ADMIN can mute
        await update.message.reply_text("You are not authorized to mute users.")
        return

    try:
        target_username_arg = context.args[0]
        duration_str = context.args[1]
    except IndexError:
        await update.message.reply_text("Usage: /mute <@username or user_id> <duration (e.g., 30m, 1h, 1d)>")
        return

    target_user_id = None
    target_username = "User" 
    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username or update.message.reply_to_message.from_user.first_name
    elif target_username_arg:
        if update.message.entities:
            for entity, text in update.message.parse_entities().items():
                if entity.type == 'text_mention':
                    target_user_id = entity.user.id
                    target_username = entity.user.username or entity.user.first_name
                    break
        if not target_user_id:
            try:
                target_user_id = int(target_username_arg)
                try:
                    member = await context.bot.get_chat_member(chat_id, target_user_id)
                    target_username = member.user.username or member.user.first_name or f"User (ID: {target_user_id})"
                except Exception:
                    target_username = f"User (ID: {target_user_id})"
            except ValueError:
                await update.message.reply_text(
                    "To mute by username, please reply to one of their messages, use a linked @mention, "
                    "or provide their numerical User ID."
                )
                return

    if not target_user_id:
        await update.message.reply_text(
            "Please reply to a user's message, use a linked @mention, or provide their User ID to mute."
        )
        return

    target_role = get_user_role(chat_id, target_user_id)
    if target_role == ADMIN:
        if muter_id != BOT_OWNER_ID : # Only Bot owner can mute an Admin
             await update.message.reply_text("Admins cannot be muted by non-owner Admins or Moderators.")
             return
    elif target_role == MODERATOR and not is_admin(chat_id, muter_id): # Moderator can't mute another moderator
        await update.message.reply_text("Moderators cannot mute other Moderators.")
        return


    duration = parse_duration(duration_str)
    if not duration:
        await update.message.reply_text("Invalid duration format. Use 'm' for minutes, 'h' for hours, 'd' for days (e.g., 30m, 1h, 1d).")
        return

    mute_end_time = time.time() + duration.total_seconds()

    if chat_id not in muted_users:
        muted_users[chat_id] = {}
    
    muted_users[chat_id][target_user_id] = mute_end_time
    logger.info(f"User {target_user_id} in chat {chat_id} muted until {datetime.fromtimestamp(mute_end_time)} by {muter_id}.")
    await update.message.reply_text(
        f"User @{target_username} (ID: {target_user_id}) has been muted for {duration_str}."
    )

async def unmute_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Unmutes a user."""
    unmuter_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not is_moderator(chat_id, unmuter_id): 
        await update.message.reply_text("You are not authorized to unmute users.")
        return

    try:
        target_username_arg = context.args[0]
    except IndexError:
        await update.message.reply_text("Usage: /unmute <@username or user_id>")
        return

    target_user_id = None
    target_username = "User"
    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username or update.message.reply_to_message.from_user.first_name
    elif target_username_arg:
        if update.message.entities:
            for entity, text in update.message.parse_entities().items():
                if entity.type == 'text_mention':
                    target_user_id = entity.user.id
                    target_username = entity.user.username or entity.user.first_name
                    break
        if not target_user_id:
            try:
                target_user_id = int(target_username_arg)
                try:
                    member = await context.bot.get_chat_member(chat_id, target_user_id)
                    target_username = member.user.username or member.user.first_name or f"User (ID: {target_user_id})"
                except Exception:
                    target_username = f"User (ID: {target_user_id})"
            except ValueError:
                await update.message.reply_text(
                    "To unmute by username, please reply to one of their messages, use a linked @mention, "
                    "or provide their numerical User ID."
                )
                return 

    if not target_user_id:
        await update.message.reply_text(
            "Please reply to a user's message, use a linked @mention, or provide their User ID to unmute."
        )
        return

    if chat_id in muted_users and target_user_id in muted_users[chat_id]:
        del muted_users[chat_id][target_user_id]
        if not muted_users[chat_id]: 
            del muted_users[chat_id]
        logger.info(f"User {target_user_id} in chat {chat_id} unmuted by {unmuter_id}.")
        await update.message.reply_text(f"User @{target_username} (ID: {target_user_id}) has been unmuted.")
    else:
        await update.message.reply_text(f"User @{target_username} (ID: {target_user_id}) is not currently muted.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text: 
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    current_time = time.time()
    user_role = get_user_role(chat_id, user_id) # Get user role once
    is_privileged_user = user_role in [ADMIN, MODERATOR]


    if spam_protection_enabled and not is_privileged_user:
        # 1. Rate Limiting
        if chat_id not in message_timestamps:
            message_timestamps[chat_id] = {}
        if user_id not in message_timestamps[chat_id]:
            message_timestamps[chat_id][user_id] = []

        message_timestamps[chat_id][user_id].append(current_time)
        message_timestamps[chat_id][user_id] = [
            ts for ts in message_timestamps[chat_id][user_id]
            if current_time - ts < RATE_LIMIT_WINDOW_SECONDS
        ]

        if len(message_timestamps[chat_id][user_id]) > MAX_MESSAGES_PER_WINDOW:
            try:
                await update.message.delete()
                logger.info(f"Deleted spam message from user {user_id} (rate limit) in chat {chat_id}.")
            except Exception as e:
                logger.error(f"Failed to delete spam message (rate limit) for user {user_id}: {e}")

            mute_end_time_spam = current_time + SPAM_MUTE_DURATION_SECONDS
            if chat_id not in muted_users:
                muted_users[chat_id] = {}
            muted_users[chat_id][user_id] = mute_end_time_spam
            
            try:
                await context.bot.send_message(
                    chat_id,
                    f"User @{update.effective_user.username or user_id} has been automatically muted for {SPAM_MUTE_DURATION_SECONDS // 60} minutes due to spamming."
                )
                logger.info(f"User {user_id} muted for spamming (rate limit) in chat {chat_id}.")
            except Exception as e:
                logger.error(f"Failed to send spam mute notification for user {user_id}: {e}")
            return 

        # 2. Forbidden Keywords Check
        if any(keyword.lower() in update.message.text.lower() for keyword in forbidden_keywords):
            try:
                await update.message.delete()
                logger.info(f"Deleted message from user {user_id} (forbidden keyword) in chat {chat_id}.")
                await update.message.reply_text(
                    f"@{update.effective_user.username or user_id}, your message was removed due to forbidden content."
                )
            except Exception as e:
                logger.error(f"Failed to delete/warn for forbidden keyword: {e}")
            return 

    if chat_id in muted_users and user_id in muted_users[chat_id]:
        mute_end_time = muted_users[chat_id][user_id]
        if current_time < mute_end_time:
            if update.message: 
                try:
                    await update.message.delete()
                    logger.info(f"Deleted message from (still) muted user {user_id} in chat {chat_id}.")
                except Exception as e:
                    if "not found" not in str(e).lower():
                        logger.error(f"Error ensuring deletion for muted user {user_id}: {e}")
            return 
        else:
            del muted_users[chat_id][user_id]
            if not muted_users[chat_id]:
                del muted_users[chat_id]
            logger.info(f"Mute expired for user {user_id} in chat {chat_id}. User unmuted.")
    
# --- Kick Functionality ---
async def kick_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    kicker_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not is_admin(chat_id, kicker_id):
        await update.message.reply_text("You are not authorized to kick users.")
        return

    try:
        target_username_arg = context.args[0]
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else None
    except IndexError:
        await update.message.reply_text("Usage: /kick <@username or user_id> [reason]")
        return

    target_user_id = None
    target_username = "User"
    if update.message.reply_to_message:
        target_user_id = update.message.reply_to_message.from_user.id
        target_username = update.message.reply_to_message.from_user.username or update.message.reply_to_message.from_user.first_name
    elif target_username_arg:
        if update.message.entities:
            for entity, text in update.message.parse_entities().items():
                if entity.type == 'text_mention':
                    target_user_id = entity.user.id
                    target_username = entity.user.username or entity.user.first_name
                    break
        if not target_user_id:
            try:
                target_user_id = int(target_username_arg)
                try:
                    member = await context.bot.get_chat_member(chat_id, target_user_id)
                    target_username = member.user.username or member.user.first_name or f"User (ID: {target_user_id})"
                except Exception:
                    target_username = f"User (ID: {target_user_id})"
            except ValueError:
                await update.message.reply_text(
                    "To kick by username, please reply, use linked @mention, or provide User ID."
                )
                return 

    if not target_user_id:
        await update.message.reply_text(
            "Please reply, use linked @mention, or provide User ID to kick."
        )
        return

    target_role = get_user_role(chat_id, target_user_id)
    if target_role == ADMIN:
        if kicker_id != BOT_OWNER_ID: # Only Bot Owner can kick an Admin
            await update.message.reply_text("Admins cannot kick other Admins unless you are the Bot Owner.")
            return
    # MODERATORs can be kicked by ADMINs (which is the kicker's role, checked above)

    if target_user_id == BOT_OWNER_ID and kicker_id != BOT_OWNER_ID: # Prevent kicking bot owner
        await update.message.reply_text("The bot owner cannot be kicked.")
        return
        
    try:
        await context.bot.kick_chat_member(chat_id=chat_id, user_id=target_user_id)
        logger.info(f"User {target_user_id} kicked from chat {chat_id} by {kicker_id}. Reason: {reason}")
        
        reply_message = f"User @{target_username} (ID: {target_user_id}) has been kicked."
        if reason:
            reply_message += f" Reason: {reason}"
        await update.message.reply_text(reply_message)
    except Exception as e:
        logger.error(f"Failed to kick user {target_user_id} from chat {chat_id}: {e}")
        await update.message.reply_text(f"Failed to kick user @{target_username}. Error: {str(e)}")


async def set_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    setter_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if setter_id != BOT_OWNER_ID and not is_admin(chat_id, setter_id) : 
        await update.message.reply_text("Only the bot owner or an Admin can set other admins.")
        return
    await set_role_command(update, context, ADMIN)

async def set_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await set_role_command(update, context, MODERATOR)

async def remove_permission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await set_role_command(update, context, USER)

# --- Command to toggle spam protection ---
async def toggle_spam_protection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global spam_protection_enabled
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not is_admin(chat_id, user_id):
        await update.message.reply_text("You are not authorized to change spam protection settings.")
        return

    spam_protection_enabled = not spam_protection_enabled
    status = "enabled" if spam_protection_enabled else "disabled"
    await update.message.reply_text(f"Spam protection is now {status}.")
    logger.info(f"Spam protection set to {status} by {user_id} in chat {chat_id}.")

# --- Reporting System Commands ---
async def report_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reporter_user = update.effective_user
    reporter_id = reporter_user.id
    chat_id = update.effective_chat.id
    current_time = time.time() 

    reason_parts = []
    target_user_id = None
    target_username = None # Will hold the display name of the target

    if update.message.reply_to_message:
        target_tg_user = update.message.reply_to_message.from_user
        target_user_id = target_tg_user.id
        target_username = target_tg_user.username or target_tg_user.first_name
        reason_parts = context.args
    elif context.args:
        target_username_arg = context.args[0]
        reason_parts = context.args[1:]
        if update.message.entities:
            for entity, text in update.message.parse_entities().items():
                if entity.type == 'text_mention': 
                    if text == target_username_arg or ("@" + entity.user.username == target_username_arg):
                        target_user_id = entity.user.id
                        target_username = entity.user.username or entity.user.first_name
                        break
        if not target_user_id:
            try:
                target_user_id = int(target_username_arg)
                try:
                    member = await context.bot.get_chat_member(chat_id, target_user_id)
                    target_username = member.user.username or member.user.first_name or f"User (ID: {target_user_id})"
                except Exception:
                    target_username = f"User (ID: {target_user_id})"
            except ValueError:
                await update.message.reply_text(
                    f"Could not identify user from '{target_username_arg}'. "
                    "Please reply, use a linked @mention, or provide a valid User ID."
                )
                return
    else:
        await update.message.reply_text("Usage: /report <@username or user_id> <reason> OR reply to a message with /report <reason>")
        return

    if not reason_parts:
        await update.message.reply_text("Please provide a reason for your report.")
        return
    reason = " ".join(reason_parts)

    if not target_user_id:
        await update.message.reply_text("Could not determine user to report. Please reply, use linked @mention or User ID.")
        return
    
    if target_user_id == reporter_id:
        await update.message.reply_text("You cannot report yourself.")
        return

    reported_user_role = get_user_role(chat_id, target_user_id)
    if reported_user_role in [ADMIN, MODERATOR]:
        await update.message.reply_text("You cannot report Admins or Moderators.")
        return

    if chat_id not in user_reports: user_reports[chat_id] = {}
    if target_user_id not in user_reports[chat_id]: user_reports[chat_id][target_user_id] = []
    
    report_data = {
        'reporter_id': reporter_id,
        'reporter_username': reporter_user.username or reporter_user.first_name,
        'reason': reason,
        'timestamp': datetime.now()
    }
    user_reports[chat_id][target_user_id].append(report_data)

    await update.message.reply_text(f"Your report against @{target_username} (ID: {target_user_id}) has been submitted. Thank you.")
    logger.info(f"User {reporter_id} reported user {target_user_id} in chat {chat_id} for: {reason}")

    num_reports = len(user_reports[chat_id][target_user_id])
    admin_notification = (
        f"📢 New Report in Chat ID {chat_id}!\n"
        f"Reported User: @{target_username} (ID: {target_user_id})\n"
        f"Reported By: @{reporter_user.username or reporter_user.first_name} (ID: {reporter_id})\n"
        f"Reason: {reason}\n"
        f"Total reports against @{target_username}: {num_reports}"
    )
    
    admins_to_notify_ids = [uid for uid, role in user_roles.get(chat_id, {}).items() if role == ADMIN]
    for admin_notify_id in admins_to_notify_ids:
        try: await context.bot.send_message(chat_id=admin_notify_id, text=admin_notification)
        except Exception as e: logger.error(f"Failed to send report PM to admin {admin_notify_id}: {e}")

    if enable_auto_actions_on_reports and reported_user_role not in [ADMIN, MODERATOR]:
        if num_reports >= REPORT_THRESHOLD_KICK:
            logger.info(f"User {target_user_id} reached kick threshold ({num_reports}/{REPORT_THRESHOLD_KICK}) in chat {chat_id}.")
            try:
                await context.bot.kick_chat_member(chat_id=chat_id, user_id=target_user_id)
                kick_msg = f"User @{target_username} (ID: {target_user_id}) has been automatically kicked due to receiving {num_reports} reports."
                await context.bot.send_message(chat_id, kick_msg)
                logger.info(f"User {target_user_id} auto-kicked from chat {chat_id}.")
                if chat_id in user_reports and target_user_id in user_reports[chat_id]:
                    del user_reports[chat_id][target_user_id]
                    if not user_reports[chat_id]: del user_reports[chat_id]
                    logger.info(f"Reports for {target_user_id} cleared after auto-kick.")
            except Exception as e:
                logger.error(f"Failed to auto-kick {target_user_id}: {e}")
                await context.bot.send_message(chat_id, f"Attempted to auto-kick @{target_username} but failed. Admins notified.")
            return 

        elif num_reports >= REPORT_THRESHOLD_MUTE:
            logger.info(f"User {target_user_id} reached mute threshold ({num_reports}/{REPORT_THRESHOLD_MUTE}) in chat {chat_id}.")
            duration_td = parse_duration(AUTO_MUTE_DURATION_ON_REPORTS)
            if duration_td:
                mute_end_time_auto = current_time + duration_td.total_seconds()
                if chat_id not in muted_users: muted_users[chat_id] = {}
                muted_users[chat_id][target_user_id] = mute_end_time_auto
                mute_msg = f"User @{target_username} (ID: {target_user_id}) has been automatically muted for {AUTO_MUTE_DURATION_ON_REPORTS} due to receiving {num_reports} reports."
                await context.bot.send_message(chat_id, mute_msg)
                logger.info(f"User {target_user_id} auto-muted until {datetime.fromtimestamp(mute_end_time_auto)}.")
            else:
                logger.error(f"Invalid AUTO_MUTE_DURATION_ON_REPORTS: {AUTO_MUTE_DURATION_ON_REPORTS}")
                await context.bot.send_message(chat_id, "Auto-mute duration misconfigured. Admins notified.")

async def list_reports(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not is_admin(chat_id, admin_id):
        await update.message.reply_text("You are not authorized to list reports.")
        return

    if not context.args:
        if chat_id not in user_reports or not any(user_reports[chat_id].values()): # Check if any user has reports
            await update.message.reply_text("There are no pending reports in this chat.")
            return
        
        reported_users_info = []
        for user_id, reports_list in user_reports[chat_id].items():
            if reports_list: 
                try:
                    member = await context.bot.get_chat_member(chat_id, user_id)
                    username = member.user.username or member.user.first_name or f"ID: {user_id}"
                except Exception: username = f"ID: {user_id}"
                reported_users_info.append(f"@{username} ({len(reports_list)} report(s))")
        
        if not reported_users_info:
            await update.message.reply_text("There are no users with active reports in this chat.")
            return
        await update.message.reply_text("Users with pending reports:\n" + "\n".join(reported_users_info))
        return

    target_username_arg = context.args[0]
    target_user_id = None
    target_username = "User"

    if update.message.reply_to_message and not target_username_arg.startswith('@'):
        target_tg_user = update.message.reply_to_message.from_user
        target_user_id = target_tg_user.id
        target_username = target_tg_user.username or target_tg_user.first_name
    elif target_username_arg:
        if update.message.entities:
            for entity, text in update.message.parse_entities().items():
                if entity.type == 'text_mention':
                     if text == target_username_arg or ("@" + entity.user.username == target_username_arg):
                        target_user_id = entity.user.id
                        target_username = entity.user.username or entity.user.first_name
                        break
        if not target_user_id:
            try:
                target_user_id = int(target_username_arg)
                try:
                    member = await context.bot.get_chat_member(chat_id, target_user_id)
                    target_username = member.user.username or member.user.first_name or f"ID: {target_user_id}"
                except Exception: target_username = f"ID: {target_user_id}"
            except ValueError:
                 await update.message.reply_text(f"Could not parse User ID from '{target_username_arg}'. Use linked @mention or valid User ID.")
                 return
    
    if not target_user_id:
        await update.message.reply_text("Could not identify user. Reply, use linked @mention, or provide User ID.")
        return

    if chat_id not in user_reports or target_user_id not in user_reports[chat_id] or not user_reports[chat_id][target_user_id]:
        await update.message.reply_text(f"No reports found for @{target_username} (ID: {target_user_id}).")
        return

    reports = user_reports[chat_id][target_user_id]
    response_text = f"Reports for @{target_username} (ID: {target_user_id}):\n"
    for i, report in enumerate(reports):
        timestamp_str = report['timestamp'].strftime("%Y-%m-%d %H:%M:%S UTC")
        response_text += (
            f"{i+1}. Reported by: @{report['reporter_username']} (ID: {report['reporter_id']}) "
            f"at {timestamp_str}\n   Reason: {report['reason']}\n"
        )
    
    if len(response_text) > 4000: 
        for part in [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]:
            await update.message.reply_text(part)
    else:
        await update.message.reply_text(response_text)

async def clear_reports(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    admin_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not is_admin(chat_id, admin_id):
        await update.message.reply_text("You are not authorized to clear reports.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /clearreports <@username or user_id>")
        return

    target_username_arg = context.args[0]
    target_user_id = None
    target_username = "User"

    if update.message.reply_to_message and not target_username_arg.startswith('@'):
        target_tg_user = update.message.reply_to_message.from_user
        target_user_id = target_tg_user.id
        target_username = target_tg_user.username or target_tg_user.first_name
    elif target_username_arg:
        if update.message.entities:
             for entity, text in update.message.parse_entities().items():
                if entity.type == 'text_mention':
                    if text == target_username_arg or ("@" + entity.user.username == target_username_arg):
                        target_user_id = entity.user.id
                        target_username = entity.user.username or entity.user.first_name
                        break
        if not target_user_id:
            try:
                target_user_id = int(target_username_arg)
                try:
                    member = await context.bot.get_chat_member(chat_id, target_user_id)
                    target_username = member.user.username or member.user.first_name or f"ID: {target_user_id}"
                except Exception: target_username = f"ID: {target_user_id}"
            except ValueError:
                 await update.message.reply_text(f"Could not parse User ID from '{target_username_arg}'. Use linked @mention or valid ID.")
                 return

    if not target_user_id:
        await update.message.reply_text("Could not identify user. Reply, use linked @mention, or provide User ID.")
        return

    if chat_id in user_reports and target_user_id in user_reports[chat_id] and user_reports[chat_id][target_user_id]:
        user_reports[chat_id][target_user_id] = [] # Clear the list of reports
        # Optionally remove the user_id key if list is empty and no other reason to keep it
        # if not user_reports[chat_id][target_user_id]: del user_reports[chat_id][target_user_id]
        # if not user_reports[chat_id]: del user_reports[chat_id]
        await update.message.reply_text(f"All reports for @{target_username} (ID: {target_user_id}) have been cleared.")
        logger.info(f"Reports cleared for {target_user_id} in chat {chat_id} by admin {admin_id}.")
    else:
        await update.message.reply_text(f"No reports found for @{target_username} (ID: {target_user_id}) to clear.")

async def toggle_auto_actions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Toggles automatic actions based on reports."""
    global enable_auto_actions_on_reports
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if not is_admin(chat_id, user_id):
        await update.message.reply_text("You are not authorized to change auto-action settings.")
        return

    enable_auto_actions_on_reports = not enable_auto_actions_on_reports
    status = "enabled" if enable_auto_actions_on_reports else "disabled"
    await update.message.reply_text(f"Automatic actions based on reports are now {status}.")
    logger.info(f"Automatic report actions set to {status} by {user_id} in chat {chat_id}.")

def main() -> None:
    application = Application.builder().token("YOUR_BOT_TOKEN").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("setadmin", set_admin))
    application.add_handler(CommandHandler("setmoderator", set_moderator))
    application.add_handler(CommandHandler("removepermission", remove_permission))
    application.add_handler(CommandHandler("mute", mute_user))
    application.add_handler(CommandHandler("unmute", unmute_user))
    application.add_handler(CommandHandler("kick", kick_user))
    application.add_handler(CommandHandler("togglespam", toggle_spam_protection))
    application.add_handler(CommandHandler("report", report_user))
    application.add_handler(CommandHandler("listreports", list_reports))
    application.add_handler(CommandHandler("clearreports", clear_reports))
    application.add_handler(CommandHandler("toggleautoactions", toggle_auto_actions))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.run_polling()

if __name__ == "__main__":
    main()
