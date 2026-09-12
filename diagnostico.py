# -*- coding: utf-8 -*-
"""Registro de diagnostico: o rastro do que aconteceu antes de um problema.

O programa se distribui por GitHub Releases, entao a falha quase sempre acontece
numa maquina que nao e a de quem escreveu o codigo. Sem rastro, o suporte vira
adivinhacao: "nao consigo reproduzir". Com o arquivo aqui, vira "me manda o
diagnostico.log".

Grava ao lado das configuracoes, em arquivo rotativo pequeno o bastante para ser
anexado num e-mail. Nada aqui pode derrubar o programa: se nem der para escrever,
o registro simplesmente nao acontece.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
import tempfile
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

NOME_ARQUIVO = "diagnostico.log"
# Tres arquivos de 512 KB: cabem varias sessoes inteiras e o conjunto nao passa
# de 1,5 MB, que ainda da para anexar num e-mail.
TAMANHO_MAXIMO = 512 * 1024
COPIAS = 3

_logger = logging.getLogger("supercaptura")
_caminho: Path | None = None


def caminho() -> Path | None:
    """Onde o registro esta sendo gravado, ou None se nao foi configurado."""
    return _caminho


def _primeira_pasta_gravavel(base_dir: Path):
    """A pasta do programa costuma servir; se for somente leitura, procura outra.

    A instalacao pode acabar numa pasta protegida (Arquivos de Programas, pen
    drive travado). Perder o registro justo nessas maquinas seria perder o
    registro de quem mais precisa dele.
    """
    candidatas = [Path(base_dir)]
    dados = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_STATE_HOME")
    if dados:
        candidatas.append(Path(dados) / "SuperCaptura")
    candidatas.append(Path(tempfile.gettempdir()) / "SuperCaptura")
    for pasta in candidatas:
        try:
            pasta.mkdir(parents=True, exist_ok=True)
            teste = pasta / ".escrita"
            teste.write_text("", encoding="ascii")
            teste.unlink()
            return pasta
        except Exception:
            continue
    return None


def configurar(base_dir, versao: str = "?") -> Path | None:
    """Liga o registro. Chamar mais de uma vez nao duplica as linhas."""
    global _caminho
    if _logger.handlers:
        return _caminho
    pasta = _primeira_pasta_gravavel(base_dir)
    if pasta is None:
        return None
    try:
        destino = pasta / NOME_ARQUIVO
        tratador = RotatingFileHandler(
            destino, maxBytes=TAMANHO_MAXIMO, backupCount=COPIAS, encoding="utf-8")
        tratador.setFormatter(logging.Formatter(
            "%(asctime)s  %(levelname)-7s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        _logger.addHandler(tratador)
        _logger.setLevel(logging.INFO)
        _logger.propagate = False
        _caminho = destino
    except Exception:
        return None
    _instalar_capturadores()
    registrar(
        f"--- Super Captura {versao} | Python {platform.python_version()} "
        f"| {platform.system()} {platform.release()} | pasta {base_dir}")
    return _caminho


def _instalar_capturadores() -> None:
    """Erro que ninguem tratou tambem entra no arquivo, com a pilha inteira."""
    anterior = sys.excepthook

    def excecao_nao_tratada(tipo, valor, pilha):
        _logger.error("Erro nao tratado", exc_info=(tipo, valor, pilha))
        anterior(tipo, valor, pilha)

    sys.excepthook = excecao_nao_tratada

    # Em thread separada o excepthook acima nao e chamado; desde o Python 3.8
    # existe um proprio para isso.
    def excecao_em_thread(args):
        _logger.error(
            f"Erro nao tratado na thread {args.thread and args.thread.name}",
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    threading.excepthook = excecao_em_thread


def registrar(mensagem: str) -> None:
    if _logger.handlers:
        _logger.info(mensagem)


def avisar(mensagem: str) -> None:
    if _logger.handlers:
        _logger.warning(mensagem)


def falha(contexto: str, excecao: BaseException | None = None) -> None:
    """Para os except que seguem em frente: o programa continua, o motivo fica.

    Estes eram os pontos cegos - o `except Exception: pass` que engole o motivo
    e deixa o usuario com um botao que simplesmente nao faz nada.
    """
    if not _logger.handlers:
        return
    if excecao is None:
        _logger.error(contexto)
    else:
        _logger.error(contexto, exc_info=excecao)


def registrar_javascript(nivel: str, mensagem: str) -> None:
    """Erro vindo da interface HTML, que roda noutro processo (o Chromium).

    Sem isto, uma excecao no meio de um traco apenas congelava a interface: nada
    na tela, nada no terminal, nada em lugar nenhum.
    """
    if not _logger.handlers:
        return
    texto = f"[interface] {mensagem}"
    if nivel == "erro":
        _logger.error(texto)
    elif nivel == "aviso":
        _logger.warning(texto)
    else:
        _logger.info(texto)
