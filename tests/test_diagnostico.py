"""Valida o registro de diagnostico: o rastro que o suporte precisa ler.

Roda sem tela e sem PySide6 - entra na rotina de testes do GitHub junto com o
atualizador e a publicacao.
"""

import importlib
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import diagnostico


class RegistroTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="super-captura-log-")
        self.root = Path(self.temporary.name)
        self.excepthook = sys.excepthook
        self.thread_excepthook = threading.excepthook
        # Cada teste comeca com o modulo zerado: configurar() e proposital
        # idempotente e nao reconfiguraria sozinho.
        importlib.reload(diagnostico)

    def tearDown(self):
        for tratador in list(diagnostico._logger.handlers):
            tratador.close()
            diagnostico._logger.removeHandler(tratador)
        sys.excepthook = self.excepthook
        threading.excepthook = self.thread_excepthook
        self.temporary.cleanup()

    def texto(self) -> str:
        return (self.root / diagnostico.NOME_ARQUIVO).read_text(encoding="utf-8")

    def test_cria_o_arquivo_com_o_cabecalho_da_sessao(self):
        destino = diagnostico.configurar(self.root, "7.6.0")
        self.assertEqual(destino, self.root / diagnostico.NOME_ARQUIVO)
        self.assertEqual(diagnostico.caminho(), destino)
        conteudo = self.texto()
        # O cabecalho e o que responde "qual versao, em que maquina" sem ter de
        # perguntar para quem relatou o problema.
        self.assertIn("Super Captura 7.6.0", conteudo)
        self.assertIn("Python", conteudo)

    def test_configurar_duas_vezes_nao_duplica(self):
        diagnostico.configurar(self.root, "7.6.0")
        diagnostico.configurar(self.root, "7.6.0")
        self.assertEqual(len(diagnostico._logger.handlers), 1)
        self.assertEqual(self.texto().count("Super Captura 7.6.0"), 1)

    def test_falha_grava_o_motivo_e_a_pilha(self):
        diagnostico.configurar(self.root, "7.6.0")
        try:
            raise ValueError("disco cheio")
        except ValueError as exc:
            diagnostico.falha("Nao foi possivel salvar a captura", exc)
        conteudo = self.texto()
        self.assertIn("Nao foi possivel salvar a captura", conteudo)
        self.assertIn("ValueError: disco cheio", conteudo)
        # Sem a pilha o registro diria o que, mas nao onde.
        self.assertIn("Traceback", conteudo)
        self.assertIn("test_diagnostico.py", conteudo)

    def test_erro_da_interface_entra_marcado(self):
        diagnostico.configurar(self.root, "7.6.0")
        diagnostico.registrar_javascript("erro", "nova-interface.js:42 x is not a function")
        diagnostico.registrar_javascript("aviso", "atributo desconhecido")
        conteudo = self.texto()
        self.assertIn("ERROR", conteudo)
        self.assertIn("[interface] nova-interface.js:42 x is not a function", conteudo)
        self.assertIn("WARNING", conteudo)

    def test_excecao_sem_tratamento_e_registrada_e_repassada(self):
        diagnostico.configurar(self.root, "7.6.0")
        repassadas = []
        anterior = sys.excepthook
        # O excepthook instalado tem de chamar quem estava antes: engolir aqui
        # esconderia o erro de quem estivesse depurando pelo terminal.
        sys.excepthook = lambda *args: repassadas.append(args)
        diagnostico._instalar_capturadores()
        try:
            raise RuntimeError("camera desconectada")
        except RuntimeError as exc:
            sys.excepthook(type(exc), exc, exc.__traceback__)
        sys.excepthook = anterior
        self.assertEqual(len(repassadas), 1)
        self.assertIn("RuntimeError: camera desconectada", self.texto())

    def test_pasta_sem_escrita_cai_para_outra_em_vez_de_quebrar(self):
        # O programa pode acabar instalado numa pasta protegida. Perder o
        # registro justo ai seria perder o registro de quem mais precisa dele.
        reserva = self.root / "reserva"
        anterior = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = str(reserva)
        try:
            inexistente = self.root / "nao-existe" / "\0invalida"
            destino = diagnostico.configurar(inexistente, "7.6.0")
        finally:
            if anterior is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = anterior
        self.assertIsNotNone(destino)
        self.assertNotEqual(destino.parent, inexistente)
        self.assertTrue(destino.exists())
        self.assertTrue(str(destino).startswith(str(reserva)))

    def test_sem_configurar_nada_e_gravado_e_nada_quebra(self):
        # As chamadas ficam espalhadas pelo app.py; se configurar() falhar, elas
        # nao podem derrubar o programa junto.
        diagnostico.registrar("mensagem")
        diagnostico.avisar("aviso")
        diagnostico.falha("contexto", ValueError("x"))
        diagnostico.registrar_javascript("erro", "mensagem")
        self.assertFalse((self.root / diagnostico.NOME_ARQUIVO).exists())

    def test_arquivo_rotaciona_e_nao_cresce_sem_limite(self):
        diagnostico.configurar(self.root, "7.6.0")
        linha = "x" * 400
        for _ in range(4000):
            diagnostico.registrar(linha)
        arquivos = list(self.root.glob(diagnostico.NOME_ARQUIVO + "*"))
        self.assertGreater(len(arquivos), 1)
        self.assertLessEqual(len(arquivos), diagnostico.COPIAS + 1)
        maior = max(caminho.stat().st_size for caminho in arquivos)
        # Com folga para a ultima linha escrita antes do corte.
        self.assertLess(maior, diagnostico.TAMANHO_MAXIMO * 1.1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
