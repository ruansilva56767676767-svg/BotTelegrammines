import os
import random
import asyncio
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    ContextTypes
)

# ============================================================
# CONFIGURAÇÕES
# ============================================================

BOT_TOKEN = os.getenv("8784168989:AAEotzECNlSroRdVqpH0ccdhGi6qHeKZYAk")
CHAT_ID = os.getenv("-1004498938792")

MINAS = 3
ESTRELAS = 4
TENTATIVAS = 2

TEMPO_VALIDACAO = 10       # segundos
TEMPO_ENTRADA = 3 * 60     # 3 minutos
INTERVALO = 60              # 1 minuto

# Estatísticas
green = 0
red = 0


# ============================================================
# GERADOR DA GRADE
# ============================================================

def gerar_grade():

    # Todas as posições da grade 5x5
    posicoes = [(linha, coluna)
                for linha in range(5)
                for coluna in range(5)]

    random.shuffle(posicoes)

    escolhidas = []

    # Tenta espalhar as estrelas
    for posicao in posicoes:

        linha, coluna = posicao

        pode_colocar = True

        for l2, c2 in escolhidas:

            distancia = abs(linha - l2) + abs(coluna - c2)

            if distancia < 2:
                pode_colocar = False
                break

        if pode_colocar:
            escolhidas.append(posicao)

        if len(escolhidas) == ESTRELAS:
            break

    # Caso não consiga completar
    if len(escolhidas) < ESTRELAS:

        for posicao in posicoes:

            if posicao not in escolhidas:
                escolhidas.append(posicao)

            if len(escolhidas) == ESTRELAS:
                break

    # Monta a grade
    linhas = []

    for linha in range(5):

        texto = ""

        for coluna in range(5):

            if (linha, coluna) in escolhidas:
                texto += "⭐"
            else:
                texto += "🟦"

        linhas.append(texto)

    return "\n".join(linhas)


# ============================================================
# FORMATAR HORÁRIO
# ============================================================

def horario(data):

    return data.strftime("%H:%M")


# ============================================================
# ENVIAR SINAL
# ============================================================

async def enviar_sinal(app):

    global green
    global red

    # --------------------------------------------------------
    # 1 - AVISO
    # --------------------------------------------------------

    mensagem_validando = await app.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "⚠️ *VALIDANDO ENTRADA*\n\n"
            "🔎 Analisando a próxima entrada...\n\n"
            "🚨 Prepare-se!\n"
            "⏳ A entrada será confirmada em 10 segundos."
        ),
        parse_mode="Markdown"
    )

    # Espera 10 segundos
    await asyncio.sleep(TEMPO_VALIDACAO)

    # --------------------------------------------------------
    # 2 - APAGA AVISO
    # --------------------------------------------------------

    try:
        await mensagem_validando.delete()
    except Exception:
        pass

    # --------------------------------------------------------
    # 3 - GERA SINAL
    # --------------------------------------------------------

    agora = datetime.now()

    validade = agora + timedelta(minutes=3)

    grade = gerar_grade()

    mensagem = (
        "✅ *ENTRADA CONFIRMADA*\n\n"

        f"{grade}\n\n"

        f"💣 *Minas:* {MINAS}\n"
        f"⏰ *Válido até:* {horario(validade)}\n"
        f"🎯 *Tentativas:* {TENTATIVAS}\n\n"

        "⚠️ Entrada encerrará automaticamente no horário informado."
    )

    await app.bot.send_message(
        chat_id=CHAT_ID,
        text=mensagem,
        parse_mode="Markdown"
    )

    # --------------------------------------------------------
    # 4 - AGUARDA 3 MINUTOS
    # --------------------------------------------------------

    await asyncio.sleep(TEMPO_ENTRADA)

    # --------------------------------------------------------
    # 5 - BOTÕES GREEN / RED
    # --------------------------------------------------------

    botoes = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🟢 GREEN",
                callback_data="green"
            ),
            InlineKeyboardButton(
                "🔴 RED",
                callback_data="red"
            )
        ]
    ])

    await app.bot.send_message(
        chat_id=CHAT_ID,
        text=(
            "📊 *RESULTADO DA ENTRADA*\n\n"
            "A validade da entrada terminou.\n\n"
            "👇 Informe o resultado:"
        ),
        parse_mode="Markdown",
        reply_markup=botoes
    )

    # --------------------------------------------------------
    # 6 - ESPERA 1 MINUTO
    # --------------------------------------------------------

    await asyncio.sleep(INTERVALO)


# ============================================================
# BOTÕES GREEN / RED
# ============================================================

async def resultado(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global green
    global red

    query = update.callback_query

    await query.answer()

    if query.data == "green":

        green += 1

        resultado_texto = "🟢 GREEN REGISTRADO!"

    else:

        red += 1

        resultado_texto = "🔴 RED REGISTRADO!"

    total = green + red

    if total > 0:
        aproveitamento = (green / total) * 100
    else:
        aproveitamento = 0

    texto = (
        f"{resultado_texto}\n\n"

        "📊 *ESTATÍSTICAS*\n\n"

        f"🟢 Green: {green}\n"
        f"🔴 Red: {red}\n"
        f"📈 Aproveitamento: {aproveitamento:.1f}%\n"
        f"📊 Total: {total}"
    )

    await query.edit_message_text(
        text=texto,
        parse_mode="Markdown"
    )


# ============================================================
# CICLO AUTOMÁTICO
# ============================================================

async def ciclo(app):

    while True:

        try:

            await enviar_sinal(app)

        except Exception as erro:

            print("ERRO:", erro)

            # Se acontecer algum erro,
            # espera antes de tentar novamente.
            await asyncio.sleep(30)


# ============================================================
# INICIAR
# ============================================================

async def iniciar(app):

    asyncio.create_task(
        ciclo(app)
    )


# ============================================================
# MAIN
# ============================================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN não configurado."
        )

    if not CHAT_ID:

        raise RuntimeError(
            "CHAT_ID não configurado."
        )

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .post_init(iniciar)
        .build()
    )

    app.add_handler(
        CallbackQueryHandler(
            resultado
        )
    )

    print("🤖 BOT INICIADO!")

    app.run_polling()


if __name__ == "__main__":
    main()