from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from datetime import datetime, timezone, timedelta
import logging

from bot.states import OnboardingStates, MainMenuStates
from bot.keyboards.onboarding_kb import (
    get_step_1_kb, get_step_2_kb, get_step_3_kb, get_step_4_kb, get_soft_resume_kb
)
from bot.keyboards.menu_kb import get_main_menu_kb
from texts.onboarding import (
    STEP_1_TEXT, STEP_2_TEXT, STEP_3_TEXT, STEP_4_TEXT, STEP_5_TEXT
)
from texts.privacy_policy import PRIVACY_POLICY_TEXT
from database.repositories.users import UserRepository
from bot.storage import SupabaseStorage

logger = logging.getLogger(__name__)
onboarding_router = Router(name="onboarding")

async def show_step(target_step: int, message_or_cb, state: FSMContext, user_id: int):
    """Helper to render a specific onboarding step and persist state in database."""
    target_msg = message_or_cb.message if isinstance(message_or_cb, CallbackQuery) else message_or_cb
    
    if target_step == 1:
        await state.set_state(OnboardingStates.step_1)
        await UserRepository.update_onboarding_step(user_id, 1)
        await UserRepository.log_event(user_id, "onboarding_step_1")
        if isinstance(message_or_cb, CallbackQuery):
            await target_msg.edit_text(STEP_1_TEXT, reply_markup=get_step_1_kb())
        else:
            await target_msg.answer(STEP_1_TEXT, reply_markup=get_step_1_kb())

    elif target_step == 2:
        await state.set_state(OnboardingStates.step_2)
        await UserRepository.update_onboarding_step(user_id, 2)
        await UserRepository.log_event(user_id, "onboarding_step_2")
        await target_msg.edit_text(STEP_2_TEXT, reply_markup=get_step_2_kb())

    elif target_step == 3:
        await state.set_state(OnboardingStates.step_3)
        await UserRepository.update_onboarding_step(user_id, 3)
        await UserRepository.log_event(user_id, "onboarding_step_3")
        await target_msg.edit_text(STEP_3_TEXT, reply_markup=get_step_3_kb())

    elif target_step == 4:
        await state.set_state(OnboardingStates.step_4)
        await UserRepository.update_onboarding_step(user_id, 4)
        await UserRepository.log_event(user_id, "onboarding_step_4")
        if isinstance(message_or_cb, CallbackQuery):
            await target_msg.edit_text(STEP_4_TEXT, reply_markup=get_step_4_kb())
        else:
            await target_msg.answer(STEP_4_TEXT, reply_markup=get_step_4_kb())


@onboarding_router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    await UserRepository.log_event(user_id, "/start")

    user = await UserRepository.get_or_create_user(user_id, username)
    consent_given = user.get("consent_given", False)

    # If consent already given -> straight to main menu
    if consent_given:
        await state.set_state(MainMenuStates.idle)
        await message.answer(STEP_5_TEXT, reply_markup=get_main_menu_kb())
        return

    # Check pause duration for soft resume (> 24 hours)
    storage: SupabaseStorage = state.storage
    last_updated = await storage.get_updated_at(user_id) if hasattr(storage, "get_updated_at") else None
    saved_step = user.get("onboarding_step", 1)

    if last_updated and saved_step in [2, 3]:
        now = datetime.now(timezone.utc)
        if now - last_updated > timedelta(hours=24):
            await state.set_state(OnboardingStates.soft_resume_prompt)
            await UserRepository.log_event(user_id, "onboarding_paused_resumed_prompt", {"saved_step": saved_step})
            await message.answer(
                "С возвращением! Продолжим оформление или начнем заново?",
                reply_markup=get_soft_resume_kb(saved_step)
            )
            return

    # Otherwise resume exactly from current step or start at step 1
    await UserRepository.log_event(user_id, "onboarding_resumed", {"step": saved_step})
    await show_step(saved_step, message, state, user_id)


@onboarding_router.callback_query(F.data == "onboarding_next_2")
async def handle_next_2(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await show_step(2, callback, state, callback.from_user.id)


@onboarding_router.callback_query(F.data == "onboarding_next_3")
async def handle_next_3(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await show_step(3, callback, state, callback.from_user.id)


@onboarding_router.callback_query(F.data == "onboarding_next_4")
async def handle_next_4(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await show_step(4, callback, state, callback.from_user.id)


@onboarding_router.callback_query(F.data == "onboarding_show_privacy")
async def handle_show_privacy(callback: CallbackQuery):
    await callback.answer()
    # Opens separate message with privacy policy without altering onboarding step
    await callback.message.answer(PRIVACY_POLICY_TEXT)


@onboarding_router.callback_query(F.data == "onboarding_consent_accept")
async def handle_consent_accepted(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await UserRepository.give_consent(user_id)
    await UserRepository.log_event(user_id, "onboarding_complete")
    
    await state.set_state(MainMenuStates.idle)
    await callback.message.edit_text(STEP_5_TEXT, reply_markup=get_main_menu_kb())
    await callback.answer("Согласие принято!")


@onboarding_router.callback_query(F.data.startswith("onboarding_resume_"))
async def handle_soft_resume(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    step = int(callback.data.split("_")[-1])
    await UserRepository.log_event(callback.from_user.id, "onboarding_resumed_accepted", {"step": step})
    await show_step(step, callback, state, callback.from_user.id)


@onboarding_router.callback_query(F.data == "onboarding_restart_confirm")
async def handle_restart_confirm(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await UserRepository.reset_consent_and_onboarding(callback.from_user.id)
    await show_step(1, callback, state, callback.from_user.id)
