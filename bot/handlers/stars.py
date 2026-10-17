from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery
import logging

from bot.keyboards.menu_kb import get_main_menu_kb

logger = logging.getLogger(__name__)
stars_router = Router(name="stars_payment")

_FREE_TEXT = (
    "Все 6 стран открыты бесплатно. "
    "Лимита на 7 дней нет, оплата Telegram Stars не принимается."
)


@stars_router.callback_query(F.data.in_({"menu_subscription_info", "pay_stars_90_days"}))
async def handle_retired_paywall(callback: CallbackQuery):
    """Old subscription buttons stay answered, but they do not open a payment."""
    await callback.answer()
    logger.info("retired paywall callback %s from %s", callback.data, callback.from_user.id)
    await callback.message.edit_text(_FREE_TEXT, reply_markup=get_main_menu_kb())


@stars_router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    """Reject a leftover Stars invoice. Launch does not sell access."""
    logger.info("rejecting pre-checkout for user %s", pre_checkout_query.from_user.id)
    await bot.answer_pre_checkout_query(
        pre_checkout_query.id,
        ok=False,
        error_message="Оплата не принимается: доступ бесплатный.",
    )


@stars_router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """Do not activate a subscription if Telegram still delivers a payment."""
    logger.info("ignoring successful_payment from %s", message.from_user.id)
    await message.answer(_FREE_TEXT, reply_markup=get_main_menu_kb())
