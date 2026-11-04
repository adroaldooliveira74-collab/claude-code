# Perito · Laudo — UrbanClin

Aplicativo de **perícias judiciais de Segurança do Trabalho (SST)**. Funciona como **site/PWA** (instalável no **celular** e no **PC**) e como **executável de desktop** (via Electron). A IA usa o **Google Gemini**.

> O Claude foi usado **apenas para construir** este aplicativo. Em uso, a IA é o **Gemini** (sua chave, no seu aparelho).

## O que o app faz
- **Importa a petição inicial (PDF)** e preenche o cadastro (processo, vara, comarca, partes, CNPJ).
- **Objeto preenchido pela IA** a partir da petição (a ART é sua, manual).
- **Quesitos importados de PDF**, na ordem **Juiz → Reclamada → Autora** (e MP).
- **Empresa reclamada + responsáveis técnicos** e **equipe pericial** (escolha perito e assistente).
- **Documentos da empresa** (LTCAT, PGR, PCMSO, LIP): leitura de PDF, busca por trechos e **checklist de conformidade**.
- **Ficha de EPI**: anexa o arquivo e aponta **lacunas de período** (alegação de neutralização por EPI sem comprovação).
- **Medições** (ruído, calor, umidade…) + **relatório do aparelho (PDF/foto)** — aceito **mesmo após o fechamento**.
- **Vistoria com fotos/vídeos**, **abertura e encerramento com hora + GPS e dupla chave** (perito + acompanhante). Ao encerrar, **fotos e descrições travam (somente leitura)**.
- **IA (Gemini)** lê fotos e documentos (à luz da função do autor), redige **legendas, caracterização, conclusão e respostas aos quesitos**, e manda para o **Relatório de Não Conformidades** o que é visto mas não é do processo.
- **Honorários calculados pela IA** (até 50 km sem deslocamento; acima, R$ 1,00/km rodado ida e volta; hotel/refeição estimados; observando o teto legal).
- **Petições de aceite e de escusa** (CPC 465/467).
- **Checklist de conformidade do laudo (CPC art. 473)** para o juízo não descartar por lacuna.
- **Exporta tudo em PDF** (laudo, relatório de NC, aceite, escusa), com o **papel timbrado UrbanClin**.
- **Backup/transferência**: exporta **todos os dados + fotos + documentos** para um arquivo; o PC importa para **liberar espaço no celular sem perder nada**.

## 1) Configurar o Gemini
1. Pegue uma chave gratuita em **https://aistudio.google.com/app/apikey**.
2. No app, aba **IA/Config**, cole a chave, escolha o modelo (ex.: `gemini-2.0-flash`) e clique **Testar conexão**.
A chave fica **somente neste aparelho** (navegador) e só é enviada ao próprio Gemini.

## 2) Usar como site / instalar no celular e no PC (PWA)
O app precisa ser servido por **HTTP(S)** (não abra o `index.html` por `file://`, senão o modo offline não liga).

**Opção simples — GitHub Pages:**
1. No GitHub, abra **Settings → Pages**.
2. Em *Source*, escolha o branch deste repositório e a pasta **/** (root). Salve.
3. Acesse a URL que o GitHub mostrar (algo como `https://<usuario>.github.io/<repo>/`).
4. No celular/PC, abra essa URL no Chrome/Edge → menu **"Instalar app"** (no iPhone: **Compartilhar → Adicionar à Tela de Início**).

Depois de instalado, funciona como app, com **câmera, GPS e offline**. (Na primeira abertura, com internet, ele guarda o necessário para rodar offline; as fontes caem para a fonte do sistema sem internet.)

## 3) Executável de desktop (.exe / AppImage / dmg)
Precisa de **Node.js** instalado.
```bash
npm install
npm start      # roda a versão desktop para testar
npm run dist   # gera o instalador em dist/ (Windows .exe, Linux AppImage, macOS dmg)
```
Observação: para um ícone perfeito no Windows, troque o ícone por um `.ico` e ajuste `build.win.icon` no `package.json`.

## 3b) APK do Android (gerado automaticamente)
Há um workflow do GitHub Actions que **compila o APK** (Capacitor, app independente/offline) sem você instalar nada:
1. No GitHub, aba **Actions → "Build Android APK" → Run workflow** (ou ele roda a cada push).
2. Ao terminar, abra a execução e baixe o arquivo em **Artifacts → `perito-laudo-apk`** (`app-debug.apk`).
3. No celular, habilite **"Instalar apps de fontes desconhecidas"** e instale o APK.

Caminho alternativo (ainda mais simples, sem Actions): hospede o PWA (Pages) e use **https://www.pwabuilder.com** — cole a URL e baixe o pacote Android.
Observação: o APK empacota o app (funciona offline); as funções de **IA (Gemini)** continuam exigindo internet. GPS/câmera podem pedir ajuste de permissão na primeira versão.

## 4) Backup e transferência celular → PC
- No celular: aba **IA/Config → Exportar tudo (backup)** gera um arquivo `.perito.json` com **todos os dados e mídias**.
- No PC: **Importar backup** (marque *abrir como leitura* se quiser só consultar).
- Depois de confirmar no PC, você pode apagar do celular para liberar espaço.

## Limitações honestas
- A IA é o **Gemini** e depende da **sua chave** e de **internet** no momento das funções de IA.
- **CNPJ na Receita** e **Projudi/PJe**: não há API aberta para peritos puxarem a petição automaticamente; a importação é pelo **PDF**. Integração automática exigiria um serviço próprio (back-end) — pode ser um próximo passo.
- **Confirme sempre a vigência** das normas, resoluções e do teto de honorários antes de assinar.

---
Identidade visual e dados profissionais: **UrbanClin — Medicina e Segurança do Trabalho**.
