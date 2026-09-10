# -*- coding: utf-8 -*-
"""Gera o cartao estilo Neofetch do perfil do GitHub (SVG claro e escuro).

Sem retrato em ASCII: so o bloco de especificacoes. O "Uptime" conta a
carreira desde jan/2008, nao a idade.

O SVG e mostrado pelo GitHub dentro de um <img>, com a fonte monoespacada
do sistema de QUEM VE (Consolas no Windows, SF Mono no Mac...), e cada uma
tem largura diferente. Por isso nada no alinhamento depende de espacos nem
da largura real da fonte:
  - a coluna dos valores tem posicao x absoluta;
  - chave + pontos sao esticados ate essa coluna com `textLength`;
  - as reguas sao <line>, nao caracteres "─".

Links: dentro de um SVG mostrado como <img> nao sao clicaveis, por isso os
contatos daqui sao so texto e o README tem uma linha de links por baixo.

Nao ha estatisticas do GitHub neste cartao (pedido do cliente). Enquanto
existiram, eram o unico motivo para a Action precisar de um token com
leitura dos repositorios privados; sairam juntas.
"""
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

SAIDA = Path(__file__).parent

INICIO_CARREIRA = date(2008, 1, 1)

CABECALHO = [
    ("OS", "Full Stack Developer · Data Scientist"),
    ("Uptime", None),  # calculado a partir de INICIO_CARREIRA
    ("Host", "Webly · Carreiras & Estágios"),
]

COMPETENCIAS = [
    ("Dados & Big Data", "SQL · Python · PySpark · Pandas · ETL · Machine Learning · Hive · "
                         "Impala · Spark SQL · Hadoop · Zeppelin · HUE"),
    ("Back-end", "FastAPI · Django · Django REST Framework · Flask · Node.js · Express · "
                 "tRPC · SQLAlchemy · Alembic · REST APIs · JWT"),
    ("Front-end", "TypeScript · React · Vite · Tailwind CSS · Astro · Jinja2 · PWA · GSAP"),
    ("Bancos e Filas", "PostgreSQL · PostGIS · SQLite · Redis · Celery · APScheduler · "
                       "Drizzle ORM"),
    ("IA & LLMs", "Agentes com tool-calling · OpenAI API · Claude API · Pipelines de ML · "
                  "MLOps · OCR (Tesseract, OpenCV)"),
    ("Integrações", "WhatsApp (Cloud API e Baileys) · Google Maps Platform · OpenStreetMap · "
                    "Pagamentos (Asaas) · Web scraping (Playwright)"),
    ("DevOps & Cloud", "Docker · Docker Compose · GitHub Actions · CI/CD · Render · Railway · "
                       "VPS Linux · Caddy · Cloudflare · AWS S3 · Sentry"),
    ("Qualidade e Segurança", "TDD · pytest · Vitest · ruff · bandit · pip-audit · OWASP · "
                              "CSP · CSRF · Rate Limiting · Criptografia · LGPD"),
    ("Visualização", "Power BI · Tableau · Superset · ECharts · Chart.js · Recharts · Jupyter"),
    ("Gestão", "Scrum · XP · Métodos Ágeis · Liderança Técnica · Gestão de Stakeholders"),
]

CONTATO = [
    ("LinkedIn", "linkedin.com/in/luiz-felipe-neves-443152215"),
    ("Website", "weit-are.com"),
    ("GitHub", "github.com/LuizFelipeVesta"),
]

# --- Geometria -------------------------------------------------------------
FONTE = 15
LINHA = 21
MARGEM_X = 32
MARGEM_TOPO = 40
# Largura por caractere no PIOR caso (fontes largas, ~0,6 em). Serve so para
# dimensionar o cartao e a quebra de linha: garante que nada transborda.
CHAR_PIOR = 9.0
# Media entre Consolas (~0,55 em) e SF Mono (~0,6 em): onde a regua de secao
# comeca depois do titulo. Um desvio aqui so mexe no espaco antes da regua.
CHAR_MEDIO = 8.6
# Folga extra a direita: com Courier New (exatamente 0,6 em) a linha mais
# longa encostava na margem. Fontes ligeiramente mais largas transbordariam.
FOLGA_DIREITA = 16

COLUNA_CHAVE_PX = 205          # chave + pontos ocupam exatamente isto
VALOR_X = MARGEM_X + COLUNA_CHAVE_PX + 10
LARGURA_VALOR_CHARS = 74       # quebra dos valores
LARGURA = int(VALOR_X + LARGURA_VALOR_CHARS * CHAR_PIOR + MARGEM_X + FOLGA_DIREITA)

TEMAS = {
    "dark_mode": dict(fundo="#0d1117", borda="#30363d", titulo="#e6edf3",
                      chave="#ffa657", valor="#a5d6ff", ponto="#6e7681", regra="#30363d"),
    "light_mode": dict(fundo="#f6f8fa", borda="#d0d7de", titulo="#1f2328",
                       chave="#953800", valor="#0a3069", ponto="#afb8c1", regra="#d0d7de"),
}


def uptime(hoje: date) -> str:
    meses = (hoje.year - INICIO_CARREIRA.year) * 12 + hoje.month - INICIO_CARREIRA.month
    anos, resto = divmod(meses, 12)
    return f"{anos} anos, {resto} meses de carreira"


def quebrar(valor: str, largura: int) -> list[str]:
    """Parte por ' · ' sem nunca cortar um item ao meio."""
    linhas, atual = [], ""
    for item in valor.split(" · "):
        candidato = item if not atual else f"{atual} · {item}"
        if len(candidato) > largura and atual:
            linhas.append(atual + " ·")
            atual = item
        else:
            atual = candidato
    linhas.append(atual)
    return linhas


def montar(hoje: date):
    el: list[dict] = []
    n = 0

    def par(chave: str, valor: str):
        nonlocal n
        partes = quebrar(valor, LARGURA_VALOR_CHARS)
        el.append(dict(tipo="par", linha=n, chave=chave, valor=partes[0]))
        n += 1
        for extra in partes[1:]:
            el.append(dict(tipo="continua", linha=n, valor=extra))
            n += 1

    def secao(titulo: str):
        nonlocal n
        n += 1
        el.append(dict(tipo="secao", linha=n, titulo=titulo))
        n += 1

    el.append(dict(tipo="prompt", linha=n))
    n += 1
    el.append(dict(tipo="regra_cheia", linha=n))
    n += 1
    for chave, valor in CABECALHO:
        par(chave, uptime(hoje) if valor is None else valor)
    secao("Competências técnicas")
    for chave, valor in COMPETENCIAS:
        par(chave, valor)
    secao("Contato")
    for chave, valor in CONTATO:
        par(chave, valor)
    return el, n


def svg(tema: dict, elementos: list[dict], total_linhas: int) -> str:
    altura = MARGEM_TOPO + (total_linhas - 1) * LINHA + 26
    fim_x = LARGURA - MARGEM_X - FOLGA_DIREITA
    partes = []
    for e in elementos:
        yy = MARGEM_TOPO + e["linha"] * LINHA
        if e["tipo"] == "prompt":
            partes.append(
                f'<text x="{MARGEM_X}" y="{yy}" font-weight="bold">'
                f'<tspan fill="{tema["titulo"]}">luizfelipe</tspan>'
                f'<tspan fill="{tema["ponto"]}">@</tspan>'
                f'<tspan fill="{tema["titulo"]}">github</tspan></text>')
        elif e["tipo"] == "regra_cheia":
            partes.append(f'<line x1="{MARGEM_X}" y1="{yy - 5}" x2="{fim_x}" y2="{yy - 5}" '
                          f'stroke="{tema["regra"]}" stroke-width="1"/>')
        elif e["tipo"] == "secao":
            inicio = MARGEM_X + len(e["titulo"]) * CHAR_MEDIO + 12
            partes.append(f'<text x="{MARGEM_X}" y="{yy}" font-weight="bold" '
                          f'fill="{tema["titulo"]}">{escape(e["titulo"])}</text>')
            partes.append(f'<line x1="{inicio:.0f}" y1="{yy - 5}" x2="{fim_x}" y2="{yy - 5}" '
                          f'stroke="{tema["regra"]}" stroke-width="1"/>')
        elif e["tipo"] == "par":
            pontos = "." * max(3, 24 - len(e["chave"]))
            partes.append(
                f'<text x="{MARGEM_X}" y="{yy}" textLength="{COLUNA_CHAVE_PX}" '
                f'lengthAdjust="spacing">'
                f'<tspan fill="{tema["chave"]}">{escape(e["chave"] + ":")}</tspan>'
                f'<tspan fill="{tema["ponto"]}"> {pontos}</tspan></text>')
            partes.append(f'<text x="{VALOR_X}" y="{yy}" fill="{tema["valor"]}">'
                          f'{escape(e["valor"])}</text>')
        elif e["tipo"] == "continua":
            partes.append(f'<text x="{VALOR_X}" y="{yy}" fill="{tema["valor"]}">'
                          f'{escape(e["valor"])}</text>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="{altura}" '
        f'viewBox="0 0 {LARGURA} {altura}" '
        "font-family=\"ui-monospace, SFMono-Regular, Consolas, 'Liberation Mono', monospace\" "
        f'font-size="{FONTE}px">'
        f'<rect x="0.5" y="0.5" width="{LARGURA - 1}" height="{altura - 1}" rx="10" '
        f'fill="{tema["fundo"]}" stroke="{tema["borda"]}"/>'
        + "".join(partes)
        + "</svg>"
    )


if __name__ == "__main__":
    hoje = date.today()
    elementos, total = montar(hoje)
    for nome, tema in TEMAS.items():
        (SAIDA / f"{nome}.svg").write_text(svg(tema, elementos, total), encoding="utf-8")
    altura = MARGEM_TOPO + (total - 1) * LINHA + 26
    print(f"cartao: {LARGURA}x{altura} | linhas: {total} | uptime: {uptime(hoje)}")
