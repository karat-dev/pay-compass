from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
import logging

from bot.states import OnboardingStates, MainMenuStates
from bot.keyboards.onboarding_kb import (
    get_step_1_kb, get_step_2_kb, get_step_3_kb, get_step_4_kb, get_soft_resume_kb
)
from bot.keyboards.menu_kb import get_main_menu_kb
from bot.keyboards.miniapp_kb import get_start_keyboard
from bot.notifications import MINIAPP_START_TEXT, ensure_menu_button, screen_from_start
from texts.onboarding import (
    STEP_1_TEXT, STEP_2_TEXT, STEP_3_TEXT, STEP_4_TEXT, STEP_5_TEXT
)
from texts.privacy_policy import PRIVACY_POLICY_TEXT
from database.repositories.users import UserRepository

logger = logging.getLogger(__name__)
onboarding_router = Router(name="onboarding")

async def _send_or_edit_step(message_or_cb, text: str, reply_markup):
    if isinstance(message_or_cb, CallbackQuery):
        try:
            if hasattr(message_or_cb.message, "edit_text"):
                await message_or_cb.message.edit_text(text, reply_markup=reply_markup)
                return
        except Exception as e:
            logger.warning(f"edit_text failed: {e}, falling back to sending new message")
        try:
            await message_or_cb.message.answer(text, reply_markup=reply_markup)
        except Exception:
            await message_or_cb.bot.send_message(message_or_cb.from_user.id, text, reply_markup=reply_markup)
    else:
        await message_or_cb.answer(text, reply_markup=reply_markup)

async def show_step(target_step: int, message_or_cb, state: FSMContext, user_id: int):
    """Helper to render a specific onboarding step and persist state in database."""
    step_data = {
        1: (OnboardingStates.step_1, STEP_1_TEXT, get_step_1_kb()),
        2: (OnboardingStates.step_2, STEP_2_TEXT, get_step_2_kb()),
        3: (OnboardingStates.step_3, STEP_3_TEXT, get_step_3_kb()),
        4: (OnboardingStates.step_4, STEP_4_TEXT, get_step_4_kb()),
    }

    if target_step not in step_data:
        target_step = 1

    fsm_state, text, kb = step_data[target_step]

    # Render message FIRST for instant UI response in Telegram
    await _send_or_edit_step(message_or_cb, text, kb)

    # Persist FSM state and analytics safely
    try:
        await state.set_state(fsm_state)
    except Exception as e:
        logger.warning(f"Failed to set FSM state for step {target_step}: {e}")

    try:
        await UserRepository.update_onboarding_step(user_id, target_step)
        await UserRepository.log_event(user_id, f"onboarding_step_{target_step}")
    except Exception as e:
        logger.warning(f"Failed to persist user onboarding step {target_step}: {e}")


@onboarding_router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    """Open the Mini App. Consent and the trip are collected inside it, not via inline buttons."""
    user_id = message.from_user.id
    screen = screen_from_start(message.text)
    try:
        await UserRepository.log_event(user_id, "/start", {"screen": screen or "trip"})
        await UserRepository.get_or_create_user(user_id)
    except Exception as exc:
        logger.warning("start user sync skipped: %s", exc)
    try:
        await state.set_state(MainMenuStates.idle)
    except Exception as exc:
        logger.warning("start state skipped: %s", exc)
    await message.answer(MINIAPP_START_TEXT, reply_markup=get_start_keyboard(screen or None))
    await ensure_menu_button(message.bot)


@onboarding_router.callback_query(F.data == "onboarding_next_2")
async def handle_next_2(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception as e:
        logger.warning(f"callback.answer failed: {e}")
    await show_step(2, callback, state, callback.from_user.id)


@onboarding_router.callback_query(F.data == "onboarding_next_3")
async def handle_next_3(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception as e:
        logger.warning(f"callback.answer failed: {e}")
    await show_step(3, callback, state, callback.from_user.id)


@onboarding_router.callback_query(F.data == "onboarding_next_4")
async def handle_next_4(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception as e:
        logger.warning(f"callback.answer failed: {e}")
    await show_step(4, callback, state, callback.from_user.id)


@onboarding_router.callback_query(F.data == "onboarding_show_privacy")
async def handle_show_privacy(callback: CallbackQuery):
    try:
        await callback.answer()
    except Exception as e:
        logger.warning(f"callback.answer failed: {e}")
    # Opens separate message with privacy policy without altering onboarding step
    await callback.message.answer(PRIVACY_POLICY_TEXT)


@onboarding_router.callback_query(F.data == "onboarding_consent_accept")
async def handle_consent_accepted(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    try:
        await callback.answer("Согласие принято!")
    except Exception as e:
        logger.warning(f"callback.answer failed: {e}")

    try:
        await callback.message.edit_text(STEP_5_TEXT, reply_markup=get_main_menu_kb())
    except Exception:
        await callback.message.answer(STEP_5_TEXT, reply_markup=get_main_menu_kb())

    try:
        await UserRepository.give_consent(user_id)
        await UserRepository.log_event(user_id, "onboarding_complete")
        await state.set_state(MainMenuStates.idle)
    except Exception as e:
        logger.warning(f"Error persisting consent: {e}")


@onboarding_router.callback_query(F.data.startswith("onboarding_resume_"))
async def handle_soft_resume(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception as e:
        logger.warning(f"callback.answer failed: {e}")
    step = int(callback.data.split("_")[-1])
    try:
        await UserRepository.log_event(callback.from_user.id, "onboarding_resumed_accepted", {"step": step})
    except Exception:
        pass
    await show_step(step, callback, state, callback.from_user.id)


@onboarding_router.callback_query(F.data == "onboarding_restart_confirm")
async def handle_restart_confirm(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.answer()
    except Exception as e:
        logger.warning(f"callback.answer failed: {e}")
    try:
        await UserRepository.reset_consent_and_onboarding(callback.from_user.id)
    except Exception:
        pass
    await show_step(1, callback, state, callback.from_user.id)
