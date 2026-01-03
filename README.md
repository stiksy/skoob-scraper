# Skoob Bookshelf Scraper / Raspador de Estante do Skoob

## Português (BR)

Script Python para extrair sua coleção de livros do Skoob (https://www.skoob.com.br) e exportar para CSV.

### Características

- Extrai todos os livros da sua estante do Skoob (filtrado para livros lidos)
- Extrai informações detalhadas dos livros incluindo ISBN, editora, ano de publicação, páginas, avaliações e mais
- Processamento paralelo para recuperação de dados mais rápida
- Paginação automática através de todas as páginas
- Exporta para CSV com codificação UTF-8

### Instalação

1. Instale as dependências do Python:
```bash
pip install -r requirements.txt
```

2. Instale os navegadores do Playwright:
```bash
playwright install
```

**Nota sobre Brotli**: A biblioteca `brotli` é necessária para descomprimir algumas respostas da API. Se você encontrar problemas ao instalar o brotli (especialmente no Windows), pode tentar instalar manualmente:
```bash
pip install brotli
```

Se ainda assim não funcionar, o script tentará usar métodos alternativos de descompressão.

### Como Usar

1. Execute o script:
```bash
python skoob_scraper.py
```

2. O script abrirá uma janela do navegador na página de login do Skoob.

3. Faça login manualmente na janela do navegador.

4. Após fazer login, volte ao terminal e pressione Enter para continuar.

5. O script irá automaticamente:
   - Extrair seu token de autorização e ID de usuário
   - Buscar todos os dados da sua estante via API
   - Buscar informações adicionais (ISBN, avaliação média, tipo de capa) das páginas individuais dos livros
   - Exportar os dados para um arquivo CSV com timestamp (ex: `skoob_estante_20240101_120000.csv`)

### Modo Debug

Para ativar o modo debug (logs detalhados e arquivos de debug):
```bash
python skoob_scraper.py --debug
```

ou

```bash
python skoob_scraper.py -d
```

No modo debug, o script salvará:
- Arquivo JSON com a resposta completa da API
- Logs detalhados de todas as operações

### Saída

O arquivo CSV conterá todas as informações disponíveis dos livros incluindo:
- Título
- Autor(es)
- ISBN
- Editora
- Ano de Publicação
- Ano de Publicação Original
- Páginas
- Tipo de Capa (Binding)
- Avaliação Média
- Minha Avaliação
- Data de Leitura
- Data de Adição
- Estantes
- Resenha
- URL do Livro

### Notas

- O script filtra apenas livros "lidos" usando a API
- Processamento paralelo é usado para buscar detalhes dos livros mais rapidamente
- Todos os dados são exportados com codificação UTF-8 para lidar corretamente com caracteres portugueses
- A janela do navegador permanecerá aberta durante a extração para que você possa monitorar o progresso
- Livros sem capa são tratados automaticamente

---

## English

A Python script to extract your book collection from Skoob (https://www.skoob.com.br) and export it to CSV.

### Features

- Extracts all books from your Skoob bookshelf (filtered for read books)
- Extracts detailed book information including ISBN, publisher, publication year, pages, ratings, and more
- Parallel processing for faster data retrieval
- Automatic pagination through all pages
- Exports to CSV with UTF-8 encoding

### Setup

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Install Playwright browsers:
```bash
playwright install
```

**Note about Brotli**: The `brotli` library is required to decompress some API responses. If you encounter issues installing brotli (especially on Windows), you can try installing it manually:
```bash
pip install brotli
```

If it still doesn't work, the script will try to use alternative decompression methods.

### Usage

1. Run the script:
```bash
python skoob_scraper.py
```

2. The script will open a browser window to the Skoob login page.

3. Log in manually in the browser window.

4. Once logged in, return to the terminal and press Enter to continue.

5. The script will automatically:
   - Extract your authorization token and user ID
   - Fetch all your bookshelf data via API
   - Fetch additional information (ISBN, average rating, binding type) from individual book pages
   - Export the data to a CSV file with a timestamp (e.g., `skoob_estante_20240101_120000.csv`)

### Debug Mode

To enable debug mode (detailed logs and debug files):
```bash
python skoob_scraper.py --debug
```

or

```bash
python skoob_scraper.py -d
```

In debug mode, the script will save:
- JSON file with the complete API response
- Detailed logs of all operations

### Output

The CSV file will contain all available book information including:
- Title
- Author(s)
- ISBN
- Publisher
- Year Published
- Original Publication Year
- Pages
- Binding
- Average Rating
- My Rating
- Date Read
- Date Added
- Shelves
- My Review
- Book URL

### Notes

- The script filters for "read" books only using the API
- Parallel processing is used to fetch book details faster
- All data is exported with UTF-8 encoding to properly handle Portuguese characters
- The browser window will remain open during extraction so you can monitor progress
- Books without cover images are handled automatically
