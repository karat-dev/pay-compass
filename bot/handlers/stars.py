from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery, Message, PreCheckoutQuery, LabeledPrice
)
import logging
import time

from config.settings import settings
from database.repositories.users import UserRepository
from bot.keyboards.country_kb import get_subscription_pay_keyboard
from bot.keyboards.menu_kb import get_main_menu_kb

logger = logging.getLogger(__name__)
stars_router = Router(name="stars_payment")

SUBSCRIPTION_DURATION_DAYS = 90  # Confirmed 90 days access model

@stars_router.callback_query(F.data == "menu_subscription_info")
async def handle_subscription_info(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    await UserRepository.log_event(user_id, "subscription_screen_opened")

    text = (
        "⭐ **ПРЕМИУМ-ДОСТУП НА 90 ДНЕЙ**\n\n"
        "С подпиской вы получаете полный контроль над платежами в поездках:\n"
        "• 🌍 **Все страны без ограничений** (не нужно ждать 7 дней)\n"
        "• ⚡ **Оперативные алерты о скаме** в реальном времени\n"
        "• 🔄 **Еженедельные обновления тарифов банков**\n"
        "• 💬 **Приоритетная линия консультаций**\n\n"
        f"Стоимость: **{settings.STARS_PRICE_90_DAYS} Telegram Stars** (~90 дней беззаботных поездок)."
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_subscription_pay_keyboard(settings.STARS_PRICE_90_DAYS),
        parse_mode="Markdown"
    )

@stars_router.callback_query(F.data == "pay_stars_90_days")
async def handle_pay_stars(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    user_id = callback.from_user.id
    await UserRepository.log_event(user_id, "click_pay_stars")

    prices = [LabeledPrice(label="Подписка на 90 дней", amount=settings.STARS_PRICE_90_DAYS)]
    payload = f"sub_90days_{user_id}_{int(time.time())}"

    # Invoices for Telegram Stars use currency="XTR" and provider_token=""
    await bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Премиум-доступ на 90 дней",
        description="Разблокировка всех стран, регулярные обновления и оперативные скам-алерты.",
        payload=payload,
        currency="XTR",
        prices=prices,
        provider_token=""
    )

@stars_router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    """Confirm the incoming Stars invoice transaction."""
    logger.info(f"Processing pre-checkout for user {pre_checkout_query.from_user.id}")
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@stars_router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """Fulfillment handler for verified Telegram Stars payment."""
    user_id = message.from_user.id
    payment = message.successful_payment

    charge_id = payment.telegram_payment_charge_id
    stars_amount = payment.total_amount

    logger.info(f"Payment successful: user={user_id}, charge_id={charge_id}, stars={stars_amount}")

    await UserRepository.activate_subscription(
        telegram_id=user_id,
        duration_days=SUBSCRIPTION_DURATION_DAYS,
        stars_paid=stars_amount,
        transaction_id=charge_id
    )

    congrats_text = (
        "🎉 **Оплата прошла успешно!**\n\n"
        f"Вам открыт **Премиум-доступ на {SUBSCRIPTION_DURATION_DAYS} дней**.\n"
        "Теперь все страны, комиссии и предупреждения о скаме доступны без ограничений."
    )
    await message.answer(congrats_text, reply_markup=get_main_menu_kb(), parse_mode="Markdown")
