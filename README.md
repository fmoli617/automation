# Automation

Projeto de estudos e prática em automação com foco em Python.

A ideia deste repositório é organizar conteúdos, exemplos e materiais de apoio para passar por fundamentos da linguagem, integrações, manipulação de arquivos e tópicos introdutórios de machine learning.

## Primeiros passos

Se esta for sua primeira vez no projeto, siga esta ordem:

1. Abra a pasta do repositório no VS Code.
2. Ative ou crie um ambiente virtual.
3. Selecione o interpretador Python do ambiente no VS Code.
4. Abra o notebook `01-fundamentos/a-hello_world.ipynb`.
5. Valide se as células executam normalmente antes de avançar para os próximos módulos.

## Pré-requisitos

- Windows com Python instalado.
- VS Code.
- Extensão Python para VS Code.
- Extensão Jupyter para VS Code.

## Ambiente virtual

Se você ainda não tiver um ambiente virtual local, crie um na raiz do projeto:

```powershell
python -m venv env
```

Para ativar no PowerShell:

```powershell
.\env\Scripts\Activate.ps1
```

Para ativar no `cmd`:

```cmd
env\Scripts\activate.bat
```

## Instalação inicial

Instale primeiro as dependências mapeadas para o projeto:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Observação: para os exemplos de SQL Server e MySQL, além do `pyodbc` você também precisa ter os drivers ODBC instalados no Windows.

## Como começar no VS Code

1. Abra a paleta de comandos.
2. Use `Python: Select Interpreter`.
3. Escolha `.\env\Scripts\python.exe`.
4. Abra `01-fundamentos/a-hello_world.ipynb`.
5. Se o VS Code pedir um kernel, selecione o mesmo ambiente virtual.

## Ordem sugerida de estudo

### 00-config

Materiais de configuração e observações para o ambiente Windows.

- `00-config/windows.md`
- `config/python/sugestoes.md`
- `config/vscode/sugestoes.md`

### 01-fundamentos

Primeiros contatos com Python e com o fluxo de estudo em notebook.

- `01-fundamentos/a-hello_world.ipynb`
- `01-fundamentos/b-variaveis.ipynb`
- `01-fundamentos/c-operadores.ipynb`

### 03-integracoes

Exemplos iniciais de integração com bancos de dados SQL.

- `03-integracoes/sql/sql_mysql.py`
- `03-integracoes/sql/sql_mysql_access.py`
- `03-integracoes/sql/sql_odbc.py`
- `03-integracoes/sql/sql_server.py`
- `03-integracoes/sql/sql_server_access.py`

### 04-manipular_extensoes

Manipulação de arquivos e conteúdo externo.

- `04-manipular_extensoes/pptx.ipynb`

### 05-machine_learning

Tópicos introdutórios e abstrações.

- `05-machine_learning/abstracoes.ipynb`

## Estrutura do projeto

```text
.
|-- 00-config/
|-- 01-fundamentos/
|-- 03-integracoes/
|-- 04-manipular_extensoes/
|-- 05-machine_learning/
|-- config/
|-- content/
|-- input/
|-- nao_subir/
|-- pyproject.toml
|-- README.md
`-- requirements.txt
```

## Padrões já existentes

- O projeto já possui configuração de `ruff` no arquivo `pyproject.toml`.
- O diretório `env/` está ignorado no git, então cada pessoa pode manter o próprio ambiente virtual local.
- Os notebooks são a porta de entrada principal para o conteúdo inicial.

## Próximos passos recomendados

- Completar o `requirements.txt` com as dependências reais do projeto.
- Expandir o `README.md` com instruções específicas para cada módulo.
- Padronizar configurações de VS Code que valham para todo o time.
