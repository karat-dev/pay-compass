from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import json
import logging

from texts.privacy_policy import PRIVACY_POLICY_TEXT
from texts.onboarding import STEP_1_TEXT
from bot.states import OnboardingStates
from bot.keyboards.onboarding_kb import get_step_1_kb
from database.repositories.users import UserRepository

logger = logging.getLogger(__name__)
legal_router = Router(name="legal_commands")

@legal_router.message(Command("privacy"))
async def cmd_privacy(message: Message):
    """Shows the official privacy policy in accordance with 152-FZ."""
    await UserRepository.log_event(message.from_user.id, "command_privacy")
    await message.answer(PRIVACY_POLICY_TEXT)

@legal_router.message(Command("restart_onboarding"))
async def cmd_restart_onboarding(message: Message, state: FSMContext):
    """Resets onboarding state and revokes prior consent, returning to Step 1."""
    user_id = message.from_user.id
    await UserRepository.reset_consent_and_onboarding(user_id)
    await state.set_state(OnboardingStates.step_1)
    await UserRepository.log_event(user_id, "onboarding_restarted")
    await message.answer(
        "Онбординг сброшен. Начнем заново:\n\n" + STEP_1_TEXT,
        reply_markup=get_step_1_kb()
    )

@legal_router.message(Command("my_data"))
async def cmd_my_data(message: Message):
    """Subject access request: returns all personal profile data stored about the user."""
    user_id = message.from_user.id
    user = await UserRepository.get_user(user_id)
    await UserRepository.log_event(user_id, "command_my_data")

    if not user:
        await message.answer("Данные о вашем профиле не найдены.")
        return

    data_summary = {
        "telegram_id": user.get("telegram_id"),
        "username": user.get("username"),
        "created_at": user.get("created_at"),
        "consent_given": user.get("consent_given"),
        "consent_date": user.get("consent_date"),
        "subscription_status": user.get("subscription_status"),
        "subscription_expires_at": user.get("subscription_expires_at")
    }

    formatted = json.dumps(data_summary, indent=2, ensure_ascii=False)
    await message.answer(
        "📄 **Ваши персональные данные (152-ФЗ):**\n\n"
        f"```json\n{formatted}\n```\n"
        "Мы храним только минимально необходимые данные для функционирования сервиса.",
        parse_mode="Markdown"
    )

@legal_router.message(Command("delete_me"))
@legal_router.message(Command("delete_account"))
async def cmd_delete_me(message: Message, state: FSMContext):
    """Right to be forgotten: immediately purges user profile, states, and history."""
    user_id = message.from_user.id
    await state.clear()
    await UserRepository.delete_user_data(user_id)
    await message.answer(
        "🗑 **Ваш аккаунт и все связанные данные успешно удалены.**\n\n"
        "Согласие на обработку данных отозвано. Чтобы начать заново, отправьте команду /start."
    )

@legal_router.message(Command("admin"))
@legal_router.message(Command("reset_limits"))
async def cmd_admin(message: Message):
    """Admin command to verify privileges and clear country access restrictions."""
    user_id = message.from_user.id
    if UserRepository.is_admin(user_id):
        from database.client import db
        await UserRepository.reset_country_limits(user_id)
        await db.update("users", {"subscription_status": "premium"}, {"telegram_id": f"eq.{user_id}"})
        await message.answer(
            f"👑 **Режим Администратора активирован!**\n\n"
            f"• Telegram ID: `{user_id}`\n"
            f"• Статус: **Premium (полный безлимитный доступ)**\n"
            f"• Лимит на 1 страну: **Сброшен**\n\n"
            "Вам открыт доступ ко всем странам, разделам и экспертным хабам без ограничений.",
            parse_mode="Markdown"
        )
    else:
        await message.answer("Эта команда доступна только администраторам сервиса.")
