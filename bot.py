import asyncio
import logging
import os
import random
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ============================================================
# CONFIGURAÇÃO
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "8784168989:AAEotzECNlSroRdVqpH0ccdhGi6qHeKZYAk")

BETANO_URL = (
    "https://www.betano.bet.br/casino/crash-games/games/"
    "mines/25456/?entrypoint=1"
)

MINES = 3
STARS = 4

VALID_SECONDS = 180       # 3 minutos
PREPARE_SECONDS = 10      # mensagem "validando"
NEXT_ROUND_DELAY = 60     # 1 minuto

ATTEMPTS = 2

# ============================================================
# LOG
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# ============================================================
# ESTADO
# ============================================================

class BotState:

    def __init__(self):
        self.running = False
        self.task = None

        self.current_signal = None

        self.green = 0
        self.red = 0

        self.total_signals = 0

        # Guarda os usuários que já votaram no sinal atual
        self.voters = set()

        # Lock para evitar dois ciclos simultâneos
        self.lock = asyncio.Lock()


state = BotState()


# ============================================================
# ADMINISTRADORES
# ============================================================

async def is_admin(update: Update) -> bool:

    if not update.effective_chat or not update.effective_user:
        return False

    try:
        member = await update.effective_chat.get_member(
            update.effective_user.id
        )

        return member.status in ("administrator", "creator")

    except Exception as e:
        logger.error("Erro verificando administrador: %s", e)
        return False


# ============================================================
# GERADOR DE ESTRELAS
# ============================================================

def generate_board():

    positions = list(range(25))

    selected = random.sample(
        positions,
        STARS
    )

    board = []

    for position in range(25):

        if position in selected:
            board.append("⭐")
        else:
            board.append("🟦")

    return board


def format_board(board):

    rows = []

    for i in range(0, 25, 5):
        rows.append(
            "".join(board[i:i + 5])
        )

    return "\n".join(rows)


# ============================================================
# HORÁRIO
# ============================================================

def get_valid_until():

    now = datetime.now()

    end = now + timedelta(
        seconds=VALID_SECONDS
    )

    return end.strftime("%H:%M")


# ============================================================
# ESTATÍSTICAS
# ============================================================

def get_percentage():

    total = state.green + state.red

    if total == 0:
        return 0

    return round(
        (state.green / total) * 100,
        1
    )


# ============================================================
# TECLADO DO SINAL
# ============================================================

def signal_keyboard():

    keyboard = [
        [
            InlineKeyboardButton(
                "🎮 ABRIR MINES — BETANO",
                url=BETANO_URL
            )
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# TECLADO DO RESULTADO
# ============================================================

def result_keyboard():

    keyboard = [
        [
            InlineKeyboardButton(
                "🟢 GREEN",
                callback_data="result_green"
            ),
            InlineKeyboardButton(
                "🔴 RED",
                callback_data="result_red"
            ),
        ]
    ]

    return InlineKeyboardMarkup(keyboard)


# ============================================================
# /START
# ============================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = (
        "🤖 *BOT MINES*\n\n"
        "Sistema de sinais para o grupo.\n\n"
        "Comandos disponíveis:\n"
        "▶️ /iniciar — iniciar sinais\n"
        "⏹ /parar — parar sinais\n"
        "📊 /stats — estatísticas\n"
        "ℹ️ /status — status do bot\n"
        "🎯 /sinal — gerar sinal manual\n"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# /STATUS
# ============================================================

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if state.running:

        status_text = "🟢 ATIVO"

    else:

        status_text = "🔴 PARADO"

    text = (
        "🤖 *STATUS DO BOT*\n\n"
        f"Estado: {status_text}\n"
        f"💣 Minas: {MINES}\n"
        f"⭐ Estrelas: {STARS}\n"
        f"🎯 Tentativas: {ATTEMPTS}\n"
        f"⏱ Validade: 3 minutos\n"
        f"📨 Sinais gerados: {state.total_signals}\n"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# /STATS
# ============================================================

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):

    total = state.green + state.red
    percentage = get_percentage()

    text = (
        "📊 *ESTATÍSTICAS*\n\n"
        f"🟢 Green: {state.green}\n"
        f"🔴 Red: {state.red}\n"
        f"📈 Total: {total}\n"
        f"🎯 Aproveitamento: {percentage}%\n"
        f"📨 Sinais: {state.total_signals}\n"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# MENSAGEM DE RESULTADO
# ============================================================

async def send_result_message(chat_id, context):

    text = (
        "🏁 *ENTRADA ENCERRADA*\n\n"
        "Informe o resultado da entrada:\n\n"
        "👇 Clique no resultado abaixo."
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=result_keyboard()
    )


# ============================================================
# CICLO
# ============================================================

async def run_cycle(chat_id, context):

    while state.running:

        try:

            # ------------------------------------------------
            # 1. VALIDANDO ENTRADA
            # ------------------------------------------------

            prepare_message = await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    "⏳ *VALIDANDO ENTRADA*\n\n"
                    "⚠️ Prepare-se!\n"
                    "Uma nova entrada está sendo analisada..."
                ),
                parse_mode="Markdown"
            )

            await asyncio.sleep(
                PREPARE_SECONDS
            )

            if not state.running:
                return

            # ------------------------------------------------
            # APAGA A MENSAGEM
            # ------------------------------------------------

            try:

                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=prepare_message.message_id
                )

            except Exception as e:

                logger.warning(
                    "Não foi possível apagar mensagem: %s",
                    e
                )

            # ------------------------------------------------
            # 2. GERA SINAL
            # ------------------------------------------------

            board = generate_board()

            board_text = format_board(
                board
            )

            valid_until = get_valid_until()

            state.total_signals += 1

            state.voters.clear()

            signal_id = state.total_signals

            state.current_signal = signal_id

            text = (
                "🟢 *ENTRADA CONFIRMADA*\n\n"
                f"{board_text}\n\n"
                f"💣 *Minas:* {MINES}\n"
                f"⏱ *Válido até:* {valid_until}\n"
                f"🎯 *Tentativas:* {ATTEMPTS}\n\n"
                "⚠️ Jogue dentro do período indicado."
            )

            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=signal_keyboard()
            )

            # ------------------------------------------------
            # 3. AGUARDA 3 MINUTOS
            # ------------------------------------------------

            await asyncio.sleep(
                VALID_SECONDS
            )

            if not state.running:
                return

            # ------------------------------------------------
            # 4. RESULTADO
            # ------------------------------------------------

            await send_result_message(
                chat_id,
                context
            )

            # ------------------------------------------------
            # 5. ESPERA 1 MINUTO
            # ------------------------------------------------

            await asyncio.sleep(
                NEXT_ROUND_DELAY
            )

        except asyncio.CancelledError:

            logger.info(
                "Ciclo cancelado."
            )

            return

        except Exception as e:

            logger.exception(
                "Erro no ciclo: %s",
                e
            )

            await asyncio.sleep(
                10
            )


# ============================================================
# /INICIAR
# ============================================================

async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update):

        await update.message.reply_text(
            "❌ Apenas administradores podem iniciar o bot."
        )

        return

    if state.running:

        await update.message.reply_text(
            "⚠️ O sistema já está funcionando."
        )

        return

    state.running = True

    chat_id = update.effective_chat.id

    state.task = asyncio.create_task(
        run_cycle(
            chat_id,
            context
        )
    )

    await update.message.reply_text(
        "🟢 *SISTEMA INICIADO*\n\n"
        "Aguardando o próximo ciclo...",
        parse_mode="Markdown"
    )


# ============================================================
# /PARAR
# ============================================================

async def parar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update):

        await update.message.reply_text(
            "❌ Apenas administradores podem parar o bot."
        )

        return

    if not state.running:

        await update.message.reply_text(
            "⚠️ O sistema já está parado."
        )

        return

    state.running = False

    if state.task:

        state.task.cancel()

        state.task = None

    state.current_signal = None

    await update.message.reply_text(
        "🔴 *SISTEMA PARADO*",
        parse_mode="Markdown"
    )


# ============================================================
# /SINAL
# ============================================================

async def sinal(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await is_admin(update):

        await update.message.reply_text(
            "❌ Apenas administradores podem gerar sinais."
        )

        return

    chat_id = update.effective_chat.id

    # Validação

    prepare_message = await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "⏳ *VALIDANDO ENTRADA*\n\n"
            "⚠️ Prepare-se!\n"
            "Nova entrada sendo analisada..."
        ),
        parse_mode="Markdown"
    )

    await asyncio.sleep(
        PREPARE_SECONDS
    )

    try:

        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=prepare_message.message_id
        )

    except Exception:
        pass

    board = generate_board()

    board_text = format_board(
        board
    )

    valid_until = get_valid_until()

    state.total_signals += 1

    state.current_signal = state.total_signals

    state.voters.clear()

    text = (
        "🟢 *ENTRADA CONFIRMADA*\n\n"
        f"{board_text}\n\n"
        f"💣 *Minas:* {MINES}\n"
        f"⏱ *Válido até:* {valid_until}\n"
        f"🎯 *Tentativas:* {ATTEMPTS}\n\n"
        "⚠️ Jogue dentro do período indicado."
    )

    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=signal_keyboard()
    )


# ============================================================
# BOTÕES GREEN / RED
# ============================================================

async def result_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    # --------------------------------------------------------
    # Evita voto duplicado
    # --------------------------------------------------------

    if user_id in state.voters:

        await query.answer(
            "⚠️ Você já registrou o resultado.",
            show_alert=True
        )

        return

    # --------------------------------------------------------
    # Verifica se existe sinal
    # --------------------------------------------------------

    if state.current_signal is None:

        await query.answer(
            "⚠️ Não existe entrada ativa.",
            show_alert=True
        )

        return

    state.voters.add(
        user_id
    )

    # --------------------------------------------------------
    # GREEN
    # --------------------------------------------------------

    if query.data == "result_green":

        state.green += 1

        result = "🟢 GREEN"

    # --------------------------------------------------------
    # RED
    # --------------------------------------------------------

    else:

        state.red += 1

        result = "🔴 RED"

    percentage = get_percentage()

    text = (
        "📊 *RESULTADO REGISTRADO*\n\n"
        f"{result}\n\n"
        f"🟢 Green: {state.green}\n"
        f"🔴 Red: {state.red}\n"
        f"📈 Aproveitamento: {percentage}%\n\n"
        "⏳ Próxima entrada em breve."
    )

    await query.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# ============================================================
# ERROS
# ============================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.exception(
        "Erro não tratado:",
        exc_info=context.error
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if (
        not BOT_TOKEN
        or BOT_TOKEN == "8784168989:AAEotzECNlSroRdVqpH0ccdhGi6qHeKZYAk"
    ):

        raise RuntimeError(
            "Configure o BOT_TOKEN antes de iniciar."
        )

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Comandos

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "iniciar",
            iniciar
        )
    )

    application.add_handler(
        CommandHandler(
            "parar",
            parar
        )
    )

    application.add_handler(
        CommandHandler(
            "stats",
            stats
        )
    )

    application.add_handler(
        CommandHandler(
            "status",
            status
        )
    )

    application.add_handler(
        CommandHandler(
            "sinal",
            sinal
        )
    )

    # Botões

    application.add_handler(
        CallbackQueryHandler(
            result_callback,
            pattern="^result_(green|red)$"
        )
    )

    application.add_error_handler(
        error_handler
    )

    logger.info(
        "Bot iniciado."
    )

    application.run_polling()


if __name__ == "__main__":
    main()