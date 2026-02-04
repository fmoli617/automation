# Python

## Instalação

- Escolha da versão

    Hoje no mercado, existe uma organização que mantem uma análise em tempo real das versões dessa linguagem, estipulando em qual status,
    a versão se encontra:

    - Bugfix: Versão estável, com correções de bugs e vulnerabilidades de segurança.
    - Security Fix: Versão estável, com correções de vulnerabilidades de segurança.
    - End of Life: Versão que não recebe mais atualizações, seja de bugs ou de segurança.
    - Pre-Release: Versão em desenvolvimento, que pode conter bugs e instabilidades.
    - Current: Versão mais recente, que pode conter novas funcionalidades e melhorias, mas ainda não é considerada estável.
    - Long Term Support (LTS): Versão que recebe suporte e atualizações por um período prolongado, geralmente 2 a 5 anos.
    - Stable: Versão estável, recomendada para uso em produção.
    - Development: Versão em desenvolvimento, que pode conter novas funcionalidades e melhorias, mas ainda não é considerada estável.
    - Legacy: Versão antiga, que pode não ser mais suportada ou recomendada para uso.
    - Experimental: Versão que contém funcionalidades experimentais, que podem ser instáveis ou não recomendadas para uso em produção.
    - Deprecated: Versão que está sendo descontinuada, e não deve mais ser utilizada em novos projetos.
    - Release Candidate (RC): Versão quase final, que está sendo testada antes do lançamento oficial.
    - Alpha/Beta: Versões iniciais de desenvolvimento, que podem conter muitos bugs e instabilidades.

    Para verificar o status atual das versões do Python, você pode visitar o site oficial: https://endoflife.date/python

- Instalação pelo site oficial:

## Utilização inicial

- Ambiente Virtual:
88
    Uma boa prática utilizada é a criação de um ambiente virtual. Esse ambiente isola as dependências do projeto (bibliotecas, frameworks, ...),
    dessa forma indicamos a instalação principal no sistema, e posteriormente, apenas isolamos o que iremos utilizat durante o prática do projeto.

    '''cmd
    python -m venv nome_do_ambiente
    '''

- Ativar ambiente:

    - Windows:
    '''cmd
    nome_do_ambiente\Scripts\activate.bat
    '''

- Arquivo de requisitos:

    Em projetos utilizando python, é comum termos um arquivo chamado `requirements.txt`. Esse arquivo lista todas as dependências necessárias para o projeto,
    facilitando a instalação e o gerenciamento dessas dependências.

    Para criar um arquivo `requirements.txt`, você pode usar o seguinte comando no terminal, **dentro do ambiente virtual**:

    '''cmd
    pip freeze > requirements.txt
    '''




