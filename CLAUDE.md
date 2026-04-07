# CLAUDE.md — FORJA3D

## Sobre o projeto
Plataforma web onde clientes descrevem um objeto por texto ou foto,
a IA gera um modelo 3D (via API Hunyuan 3D da Tencent Cloud), o cliente
visualiza e aprova, paga via Mercado Pago (PIX/cartão), e a peça é
impressa em uma Bambu Lab X1 Carbon e enviada pelos Correios para todo o Brasil.

## Tech stack
- Frontend: Next.js 15, TypeScript, Tailwind CSS, Google model-viewer
- Backend: Python 3.12, FastAPI, PostgreSQL (asyncpg)
- APIs: Tencent Cloud Hunyuan 3D Global, Mercado Pago, Correios
- Impressora: Bambu Lab X1 Carbon (via bambulabs-api, MQTT/FTP local)
- Deploy: Vercel (frontend), Railway (backend)

## Estrutura do projeto
```
forja3d/
├── CLAUDE.md
├── frontend/                    # Next.js 15 (deploy na Vercel)
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx       # Layout global (DM Sans + Space Mono)
│   │   │   ├── page.tsx         # Landing page
│   │   │   ├── criar/page.tsx   # Tela de geração 3D
│   │   │   ├── preview/page.tsx # Preview 3D + config material/escala
│   │   │   ├── checkout/page.tsx # Pagamento
│   │   │   ├── pedido/[id]/page.tsx # Acompanhamento
│   │   │   └── admin/page.tsx   # Painel administrativo
│   │   ├── components/
│   │   │   ├── ModelViewer.tsx   # Wrapper do <model-viewer>
│   │   │   ├── PriceCalculator.tsx
│   │   │   ├── MaterialSelector.tsx
│   │   │   └── OrderTracker.tsx
│   │   └── lib/
│   │       ├── api.ts           # Chamadas ao backend
│   │       └── utils.ts
│   └── .env.local
├── backend/                     # FastAPI (deploy no Railway)
│   ├── main.py                  # App FastAPI principal
│   ├── routers/
│   │   ├── generate.py          # POST /api/generate
│   │   ├── orders.py            # CRUD pedidos
│   │   ├── payment.py           # Webhook Mercado Pago
│   │   └── shipping.py          # Cálculo frete Correios
│   ├── services/
│   │   ├── hunyuan.py           # Integração Tencent Cloud Hunyuan 3D
│   │   ├── mesh_repair.py       # Reparo de malha com trimesh
│   │   ├── price_calculator.py  # Cálculo de preço
│   │   ├── mercadopago.py       # Integração pagamento
│   │   └── correios.py          # Cálculo de frete
│   ├── models/
│   │   └── schemas.py           # Pydantic models
│   ├── database.py              # SQLAlchemy + SQLite
│   └── .env
└── printer-agent/               # Script local (PC da impressora)
    ├── agent.py                 # Monitora fila + envia para X1
    └── config.json              # IP, serial, access code da X1
```

## Convenções
- Português brasileiro em todo o UI, comentários em português
- snake_case para Python, camelCase para TypeScript
- Variáveis de ambiente em .env, nunca hardcoded
- Preços sempre em centavos no backend, formatados no frontend
- Todos os endpoints REST retornam JSON: { success: bool, data: any, error: string | null }
- Usar async/await em todo o backend (httpx, SQLAlchemy async)

## Design do frontend
- Tema escuro (#0a0a0a fundo), acentos teal (#4ECDC4, #44B09E)
- Fontes: DM Sans (body), Space Mono (números/código)
- Bordas sutis rgba(255,255,255,0.08), border-radius 16-20px
- Animações suaves com CSS (slideUp, fadeIn, gradientMove)
- Noise texture overlay sutil no fundo
- Botões com gradiente teal, hover com elevação e glow
- Mobile-first, responsivo

## Restrições da impressora Bambu Lab X1 Carbon
- Volume máximo: 256 x 256 x 256 mm
- Materiais suportados: PLA (R$0.10/g), PETG (R$0.11/g), TPU (R$0.18/g)
- Nozzle: 0.4mm, temperatura máxima 300°C
- Velocidade máxima: 500mm/s
- Formato de arquivo: .3mf (fatiado pelo BambuStudio CLI)

## Fórmula de preço
```
custo_material = peso_g × custo_por_g_do_material
custo_energia = tempo_impressao_h × 0.50
custo_api = 1.80  # custo da geração 3D Hunyuan
custo_embalagem = 3.00
custo_total = custo_material + custo_energia + custo_api + custo_embalagem
preco_final = custo_total × 1.8  # margem de 80%
```

## Fluxo principal do sistema
1. Cliente acessa o site e descreve objeto (texto) ou envia foto
2. Frontend chama POST /api/generate com prompt ou imagem base64
3. Backend chama API Tencent Cloud Hunyuan 3D → recebe task_id
4. Backend faz polling até status FINISHED → baixa arquivo GLB
5. Backend repara malha com trimesh (fix_normals, fill_holes, watertight check)
6. Backend calcula peso estimado (volume × densidade do material)
7. Frontend exibe preview 3D com <model-viewer> (GLB direto)
8. Cliente escolhe material e escala → frontend calcula preço em tempo real
9. Cliente clica "Imprimir" → POST /api/orders cria pedido
10. Backend calcula frete via API Correios (PAC, origem CEP 28035-030)
11. Frontend redireciona para checkout Mercado Pago (PIX ou cartão)
12. Webhook do Mercado Pago confirma pagamento → pedido status = PAGO
13. Printer-agent detecta pedido pago → fatia STL → envia para X1 Carbon
14. Impressora imprime → agent monitora progresso via MQTT
15. Peça pronta → embala → envia pelos Correios → atualiza tracking

## API Tencent Cloud Hunyuan 3D
- Endpoint: usar SDK oficial tencentcloud-sdk-python
- Região: ap-singapore
- Action: SubmitHunyuan3DModelGenerationJob
- Parâmetros: Prompt (texto) ou ImageUrl (imagem), GenerateType=Normal
- Cada geração consome 20 créditos
- Saída: arquivo GLB com texturas

## API Mercado Pago
- SDK: mercadopago (pip install mercadopago)
- Checkout Transparente com API de Pagamentos
- Métodos: PIX (QR Code) e Cartão de crédito
- Webhook URL: POST /api/payment/webhook
- Public Key no frontend, Access Token no backend

## Variáveis de ambiente necessárias
### Frontend (.env.local)
- NEXT_PUBLIC_API_URL (URL do backend)
- NEXT_PUBLIC_MP_PUBLIC_KEY (Public Key do Mercado Pago)

### Backend (.env)
- TENCENT_SECRET_ID
- TENCENT_SECRET_KEY
- MP_ACCESS_TOKEN
- CORREIOS_CEP_ORIGEM=28035030
- DATABASE_URL=sqlite:///./forja3d.db
- ADMIN_PASSWORD
- STORAGE_PATH=./uploads
