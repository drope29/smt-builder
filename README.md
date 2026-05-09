# SmartBet Builder

Passo a passo para rodar o projeto localmente.

---

## 1. Clonar o projeto

```bash
git clone URL_DO_REPOSITORIO
cd smb-builder
```

---

## 2. Rodar o backend

Entre na pasta do backend:

```bash
cd backend
```

Crie o ambiente virtual:

```bash
python -m venv venv
```

Ative o ambiente virtual:

```bash
venv\Scripts\Activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Crie um arquivo `.env` dentro da pasta `backend`:

```env
ODDS_API_KEY=SUA_CHAVE_DA_THE_ODDS_API
API_FOOTBALL_KEY=SUA_CHAVE_DA_API_FOOTBALL
API_FOOTBALL_MAX_CALLS_PER_RUN=40
```

Rode o backend:

```bash
uvicorn main:app --reload
```

O backend ficará em:

```txt
http://127.0.0.1:8000
```

A documentação da API ficará em:

```txt
http://127.0.0.1:8000/docs
```

---

## 3. Rodar o frontend

Abra outro terminal na raiz do projeto e entre na pasta do frontend:

```bash
cd frontend
```

Instale as dependências:

```bash
npm install
```

Rode o frontend:

```bash
npm run dev
```

O frontend ficará em:

```txt
http://localhost:5173
```

---

## 4. Rodar o projeto completo

Deixe dois terminais abertos.

### Terminal 1 — Backend

```bash
cd backend
venv\Scripts\Activate
uvicorn main:app --reload
```

### Terminal 2 — Frontend

```bash
cd frontend
npm run dev
```

Depois abra no navegador:

```txt
http://localhost:5173
```
