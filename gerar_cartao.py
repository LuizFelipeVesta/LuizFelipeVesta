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

Estatisticas: lidas com o `gh` CLI, que usa o token do ambiente (GH_TOKEN na
GitHub Action, a sessao do `gh auth login` localmente). O script nunca le nem
escreve o token. So TOTAIS vao para o cartao -- nenhum nome de repositorio.

Porque os commits NAO vem de `contributionsCollection.totalCommitContributions`:
esse campo so soma os repositorios publicos e poe todo o trabalho privado em
`restrictedContributionsCount`, sem distinguir commits de issues ou PRs.
Medido na primeira versao: dava 38 commits, quando so a MIRA tem 451 do
Luiz. Por isso os commits contam-se repositorio a repositorio, filtrados
pelo autor -- o que tambem deixa de fora os commits de colaboradores.
"""
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime, timezone
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
    ("GitHub", "github.com/LuizFelipeVesta"),
]

ESTATISTICAS_INDISPONIVEIS = [
    ("Repositórios", "…"),
    ("Commits", "…"),
    ("Contribuições", "…"),
    ("Linhas de código", "…"),
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


# --- Estatisticas ------------------------------------------------------------
Q_VIEWER = "query { viewer { login createdAt } }"
Q_REPOS = """
query($cursor: String) {
  viewer {
    repositories(first: 100, after: $cursor,
                 ownerAffiliations: [OWNER, COLLABORATOR, ORGANIZATION_MEMBER]) {
      totalCount
      nodes { nameWithOwner }
      pageInfo { hasNextPage endCursor }
    }
  }
}"""
# O total do calendario e o numero "X contribuicoes" do perfil: inclui o
# trabalho privado quando a opcao "Private contributions" esta ligada.
Q_CALENDARIO = """
query($de: DateTime!, $ate: DateTime!) {
  viewer {
    contributionsCollection(from: $de, to: $ate) {
      contributionCalendar { totalContributions }
    }
  }
}"""


def gh(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", "api", *args], capture_output=True, text=True,
                          encoding="utf-8", timeout=120)


def gh_json(args: list[str]):
    r = gh(args)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {args[0]}: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout) if r.stdout.strip() else None


def graphql(query: str, **variaveis):
    args = ["graphql", "-f", f"query={query}"]
    for chave, valor in variaveis.items():
        args += ["-F", f"{chave}={'null' if valor is None else valor}"]
    return gh_json(args)["data"]


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def commits_do_autor(nwo: str, login: str) -> int:
    r = gh([f"repos/{nwo}/commits?author={login}&per_page=100", "--paginate", "--jq", "length"])
    if r.returncode != 0:
        if "empty" in r.stderr.lower():  # 409: repositorio sem nenhum commit
            return 0
        raise RuntimeError(f"commits de {nwo}: {r.stderr.strip()[:200]}")
    return sum(int(x) for x in r.stdout.split())


def linhas_do_autor(nwo: str, login: str) -> tuple[int, int]:
    contribuidores = None
    for _ in range(8):
        contribuidores = gh_json([f"repos/{nwo}/stats/contributors"])
        # 202 devolve {} enquanto o GitHub calcula; 204 (repo vazio) devolve nada.
        if not isinstance(contribuidores, dict):
            break
        time.sleep(3)
    adicoes = remocoes = 0
    if isinstance(contribuidores, list):
        for c in contribuidores:
            if ((c.get("author") or {}).get("login") or "").lower() == login.lower():
                for semana in c.get("weeks", []):
                    adicoes += semana.get("a", 0)
                    remocoes += semana.get("d", 0)
    return adicoes, remocoes


def estatisticas() -> list[tuple[str, str]]:
    viewer = graphql(Q_VIEWER)["viewer"]
    login, criado = viewer["login"], viewer["createdAt"]

    repos, cursor, total = [], None, 0
    while True:
        dados = graphql(Q_REPOS, cursor=cursor)["viewer"]["repositories"]
        total = dados["totalCount"]
        repos += [n["nameWithOwner"] for n in dados["nodes"]]
        if not dados["pageInfo"]["hasNextPage"]:
            break
        cursor = dados["pageInfo"]["endCursor"]

    # contributionsCollection aceita no maximo um ano por consulta.
    agora = datetime.now(timezone.utc)
    contribuicoes = 0
    for ano in range(int(criado[:4]), agora.year + 1):
        de = criado if ano == int(criado[:4]) else f"{ano}-01-01T00:00:00Z"
        if ano == agora.year:
            ate = agora.strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            ate = f"{ano}-12-31T23:59:59Z"
        colecao = graphql(Q_CALENDARIO, de=de, ate=ate)["viewer"]["contributionsCollection"]
        contribuicoes += colecao["contributionCalendar"]["totalContributions"]

    commits = adicoes = remocoes = 0
    for nwo in repos:
        commits += commits_do_autor(nwo, login)
        a, d = linhas_do_autor(nwo, login)
        adicoes += a
        remocoes += d

    return [
        ("Repositórios", fmt(total)),
        ("Commits", fmt(commits)),
        ("Contribuições", fmt(contribuicoes)),
        ("Linhas de código", f"{fmt(adicoes - remocoes)} (+{fmt(adicoes)} / −{fmt(remocoes)})"),
    ]


# --- Layout ------------------------------------------------------------------
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


def montar(hoje: date, stats: list[tuple[str, str]]):
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
    secao("GitHub Stats")
    for chave, valor in stats:
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
    try:
        stats = estatisticas()
    except Exception as erro:  # noqa: BLE001
        # Na Action (CARTAO_ESTRITO=1) falha alto: nao se publica um cartao
        # degradado por causa de um token expirado. Localmente, segue com "…".
        if os.environ.get("CARTAO_ESTRITO") == "1":
            raise
        print(f"aviso: estatisticas indisponiveis ({erro})", file=sys.stderr)
        stats = ESTATISTICAS_INDISPONIVEIS
    elementos, total = montar(hoje, stats)
    for nome, tema in TEMAS.items():
        (SAIDA / f"{nome}.svg").write_text(svg(tema, elementos, total), encoding="utf-8")
    altura = MARGEM_TOPO + (total - 1) * LINHA + 26
    print(f"cartao: {LARGURA}x{altura} | linhas: {total} | uptime: {uptime(hoje)}")
    for chave, valor in stats:
        print(f"  {chave}: {valor}")
