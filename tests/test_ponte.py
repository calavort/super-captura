"""Confere que a interface e o programa falam a mesma lingua.

A interface chama o programa por nome, em tempo de execucao: um nome errado nao
quebra nada visivel - o botao simplesmente nao faz nada. E justamente o tipo de
falha que so aparece quando o usuario reclama. Aqui os dois lados sao lidos e
comparados, sem precisar de tela.
"""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

APP = (ROOT / "app.py").read_text(encoding="utf-8")
JS = (ROOT / "interface" / "nova-interface.js").read_text(encoding="utf-8")
HTML = (ROOT / "interface" / "interface-super-captura.html").read_text(encoding="utf-8")


def slots_do_programa() -> set[str]:
    """Os metodos marcados com @Slot, que sao os visiveis para a interface."""
    nomes = set()
    for trecho in re.finditer(r"@Slot\([^)]*\)\s*\n\s*def\s+([A-Za-z_]\w*)", APP):
        nomes.add(trecho.group(1))
    return nomes


class PonteTests(unittest.TestCase):
    def test_toda_chamada_da_interface_existe_no_programa(self):
        slots = slots_do_programa()
        self.assertIn("savePreferences", slots, "a leitura dos @Slot falhou")
        chamadas = set(re.findall(r"pyBridge\.(\w+)\s*\(", JS))
        # Duas chamadas sao montadas em tempo de execucao (pyBridge[metodo]):
        # o nome delas aparece so como texto, e tem de valer igual.
        chamadas |= {nome for nome in re.findall(r'"(\w+)"', JS) if nome in slots}
        faltando = sorted(nome for nome in chamadas if nome not in slots)
        self.assertEqual(faltando, [], f"a interface chama o que o programa nao tem: {faltando}")

    def test_nenhum_slot_fica_sem_ninguem_para_chamar(self):
        """Ponta solta do outro lado: metodo exposto que ninguem usa."""
        slots = slots_do_programa()
        usados = set(re.findall(r"pyBridge\.(\w+)\s*\(", JS))
        usados |= {nome for nome in re.findall(r'"(\w+)"', JS) if nome in slots}
        usados |= set(re.findall(r"appBridge\('(\w+)'\)", HTML))
        orfaos = sorted(nome for nome in slots if nome not in usados)
        self.assertEqual(orfaos, [], f"slot que a interface nunca chama: {orfaos}")

    def test_todo_appBridge_do_html_existe(self):
        slots = slots_do_programa()
        pedidos = set(re.findall(r"appBridge\('(\w+)'\)", HTML))
        self.assertGreater(len(pedidos), 5, "nenhum appBridge encontrado no HTML")
        faltando = sorted(nome for nome in pedidos if nome not in slots)
        self.assertEqual(faltando, [], f"botao chamando o que nao existe: {faltando}")

    def test_todo_onclick_do_html_aponta_para_funcao_que_existe(self):
        # As funcoes da interface sao declaradas no JS; appBridge e switchTab
        # tambem. O que o HTML chamar tem de estar la.
        declaradas = set(re.findall(r"^function\s+(\w+)", JS, re.M))
        declaradas |= set(re.findall(r"^(?:const|let)\s+(\w+)\s*=\s*(?:\([^)]*\)|\w+)\s*=>", JS, re.M))
        chamadas = set()
        for acao in re.findall(r'onclick="([^"]*)"', HTML):
            nome = re.match(r"\s*([A-Za-z_$][\w$]*)\s*\(", acao)
            if nome and not acao.startswith("this."):
                chamadas.add(nome.group(1))
        self.assertGreater(len(chamadas), 15, "poucos onclick encontrados")
        faltando = sorted(nome for nome in chamadas if nome not in declaradas)
        self.assertEqual(faltando, [], f"onclick sem funcao correspondente: {faltando}")

    def test_o_programa_nao_chama_funcao_que_a_interface_nao_tem(self):
        # O caminho contrario: runJavaScript com nome de funcao que sumiu.
        declaradas = set(re.findall(r"^function\s+(\w+)", JS, re.M))
        chamadas = set(re.findall(r"typeof (\w+) === 'function'", APP))
        chamadas |= set(re.findall(r'runJavaScript\(\s*"(\w+)\(', APP))
        self.assertGreater(len(chamadas), 2, "nenhuma chamada do programa para a interface")
        faltando = sorted(nome for nome in chamadas if nome not in declaradas)
        self.assertEqual(faltando, [], f"o programa chama o que a interface nao tem: {faltando}")

    def test_toda_ferramenta_do_html_e_conhecida_pelo_codigo(self):
        ferramentas = set(re.findall(r'data-tool="(\w+)"', HTML))
        self.assertGreater(len(ferramentas), 10, "poucas ferramentas encontradas")
        # O JS precisa citar cada uma em algum lugar: num conjunto, num menu ou
        # num ramo de desenho. Ferramenta que so existe no HTML e botao morto.
        orfas = sorted(nome for nome in ferramentas if f'"{nome}"' not in JS and f"'{nome}'" not in JS)
        self.assertEqual(orfas, [], f"botao de ferramenta que o codigo nao conhece: {orfas}")

    def test_todo_id_usado_pelo_codigo_existe_no_html(self):
        ids = set(re.findall(r'\bid="([^"]+)"', HTML))
        usados = set(re.findall(r'byId\("([^"]+)"\)', JS))
        usados |= set(re.findall(r"getElementById\(\"([^\"]+)\"\)", JS))
        self.assertGreater(len(usados), 20, "poucos byId encontrados")
        # Metade da caixa de cores e montada pelo proprio JS, entao os ids dela
        # nascem la: valem tanto quanto os que estao no HTML.
        ids |= set(re.findall(r'id="([^"]+)"', JS))
        ids |= set(re.findall(r'\.id = "([^"]+)"', JS))
        faltando = sorted(nome for nome in usados if nome not in ids)
        self.assertEqual(faltando, [], f"o codigo procura id que nao existe: {faltando}")


if __name__ == "__main__":
    unittest.main(verbosity=1)
