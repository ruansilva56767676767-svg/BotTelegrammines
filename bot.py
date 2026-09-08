import os
import asyncio
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv('BOT_TOKEN', '8784168989:AAEotzECNlSroRdVqpH0ccdhGi6qHeKZYAk')
MINES = 3
STARS = 4
ATTEMPTS = 2
PREPARE_SECONDS = 10
VALID_SECONDS = 180
RESTART_SECONDS = 60

running = False
cycle_task = None
chat_id = None
green_total = 0
red_total = 0
round_green = 0
round_red = 0
round_number = 0


def gerar_grade():
    posicoes = list(range(25))
    random.shuffle(posicoes)
    escolhidas = []
    linhas = [0] * 5
    colunas = [0] * 5
    for pos in posicoes:
        linha, coluna = divmod(pos, 5)
        if linhas[linha] >= 2 or colunas[coluna] >= 2:
            continue
        escolhidas.append(pos)
        linhas[linha] += 1
        colunas[coluna] += 1
        if len(escolhidas) == STARS:
            break
    if len(escolhidas) < STARS:
        for pos in posicoes:
            if pos not in escolhidas:
                escolhidas.append(pos)
                if len(escolhidas) == STARS:
                    break
    escolhidas = set(escolhidas)
    return '\n'.join(
        ''.join('⭐' if r * 5 + c in escolhidas else '🟦' for c in range(5))
        for r in range(5)
    )


def estatisticas():
    total = green_total + red_total
    aproveitamento = green_total / total * 100 if total else 0
    return (
        '📊 <b>ESTATÍSTICAS</b>\n\n'
        f'🟢 GREEN: <b>{green_total}</b>\n'
        f'🔴 RED: <b>{red_total}</b>\n\n'
        f'📈 Aproveitamento: <b>{aproveitamento:.1f}%</b>'
    )


async def apagar_mensagem(bot, chat, message_id):
    try:
        await bot.delete_message(chat_id=chat, message_id=message_id)
    except Exception:
        pass


async def enviar_sinal(bot, chat):
    global round_number, round_green, round_red
    round_number += 1
    round_green = 0
    round_red = 0

    aviso = await bot.send_message(
        chat_id=chat,
        text=(
            '⚠️ <b>VALIDANDO ENTRADA...</b>\n\n'
            '🚨 Prepare-se!\n\n'
            f'O próximo sinal será enviado em <b>{PREPARE_SECONDS} segundos</b>.'
        ),
        parse_mode='HTML'
    )

    await asyncio.sleep(PREPARE_SECONDS)
    await apagar_mensagem(bot, chat, aviso.message_id)

    inicio = datetime.now()
    validade = inicio + timedelta(seconds=VALID_SECONDS)
    grade = gerar_grade()

    await bot.send_message(
        chat_id=chat,
        text=(
            '✅ <b>ENTRADA CONFIRMADA</b>\n\n'
            f'{grade}\n\n'
            f'💣 Minas: <b>{MINES}</b>\n'
            f'⏱️ Válido até: <b>{validade.strftime("%H:%M")}</b>\n'
            f'🎯 Tentativas: <b>{ATTEMPTS}</b>\n\n'
            '⚠️ Use gerenciamento de banca.'
        ),
        parse_mode='HTML'
    )

    await asyncio.sleep(VALID_SECONDS)

    botoes = InlineKeyboardMarkup([[
        InlineKeyboardButton('🟢 GREEN', callback_data=f'green_{round_number}'),
        InlineKeyboardButton('🔴 RED', callback_data=f'red_{round_number}')
    ]])

    await bot.send_message(
        chat_id=chat,
        text='⏰ <b>ENTRADA ENCERRADA</b>\n\nComo foi o resultado dessa entrada?',
        parse_mode='HTML',
        reply_markup=botoes
    )

    await asyncio.sleep(RESTART_SECONDS)


async def ciclo(application):
    global running
    while running:
        try:
            if chat_id is None:
                running = False
                break
            await enviar_sinal(application.bot, chat_id)
        except asyncio.CancelledError:
            break
        except Exception as erro:
            print('Erro no ciclo:', repr(erro))
            await asyncio.sleep(10)


async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global running, cycle_task, chat_id
    chat_id = update.effective_chat.id
    if running:
        await update.message.reply_text('🟢 O bot já está funcionando.')
        return
    running = True
    cycle_task = asyncio.create_task(ciclo(context.application))
    await update.message.reply_text(
        '🟢 <b>BOT INICIADO</b>\n\nO primeiro aviso será enviado automaticamente.',
        parse_mode='HTML'
    )


async def parar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global running, cycle_task
    running = False
    if cycle_task and not cycle_task.done():
        cycle_task.cancel()
    cycle_task = None
    await update.message.reply_text('🔴 <b>BOT PARADO</b>.', parse_mode='HTML')


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(estatisticas(), parse_mode='HTML')


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global green_total, red_total
    green_total = 0
    red_total = 0
    await update.message.reply_text('♻️ <b>ESTATÍSTICAS ZERADAS</b>', parse_mode='HTML')


async def resultado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global green_total, red_total, round_green, round_red
    query = update.callback_query
    await query.answer()
    tipo = query.data.split('_', 1)[0]
    if tipo == 'green':
        green_total += 1
        round_green += 1
    elif tipo == 'red':
        red_total += 1
        round_red += 1
    try:
        await query.edit_message_text(
            text=(
                '📊 <b>RESULTADO REGISTRADO</b>\n\n'
                f'🟢 Green nesta entrada: <b>{round_green}</b>\n'
                f'🔴 Red nesta entrada: <b>{round_red}</b>\n\n'
                f'📈 Total Green: <b>{green_total}</b>\n'
                f'📉 Total Red: <b>{red_total}</b>'
            ),
            parse_mode='HTML'
        )
    except Exception:
        pass


def main():
    if not TOKEN or TOKEN == '8784168989:AAEotzECNlSroRdVqpH0ccdhGi6qHeKZYAk':
        raise RuntimeError('Defina a variável BOT_TOKEN com o token do BotFather.')
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler('iniciar', iniciar))
    application.add_handler(CommandHandler('parar', parar))
    application.add_handler(CommandHandler('status', status))
    application.add_handler(CommandHandler('reset', reset))
    application.add_handler(CallbackQueryHandler(resultado, pattern=r'^(green|red)_\d+$'))
    print('🤖 Bot online!')
    application.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
