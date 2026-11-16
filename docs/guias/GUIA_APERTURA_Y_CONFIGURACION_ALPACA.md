# Guía Maestra: Apertura de Cuenta y Configuración de Alpaca Markets para Argentina

> **Documento:** Guía Operativa y de Configuración  
> **Proyecto:** `trading_ollama`  
> **Broker:** Alpaca Securities LLC / Alpaca Crypto LLC ([alpaca.markets](https://alpaca.markets))  
> **Propósito:** Registro, verificación de identidad (KYC), fondeo con stablecoins (USDT/USDC) y obtención de API Keys para trading multiactivo 100% automatizado en Python.

---

## 1. ¿Por qué Alpaca Markets para este Proyecto?

1. **Multiactivo Unificado:** Permite operar en una sola cuenta y bajo una misma API:
   - **Acciones de Wall Street (NYSE / Nasdaq):** Apple (AAPL), Nvidia (NVDA), Tesla (TSLA), Microsoft (MSFT), etc.
   - **ETFs Institucionales:** S&P 500 (SPY), Nasdaq 100 (QQQ), Bonos del Tesoro (TLT).
   - **Criptomonedas:** Bitcoin (BTC), Ethereum (ETH), Solana (SOL).
2. **Cero Comisiones Fijas en Acciones:** No cobra comisiones de custodia mensual ni tarifas por mantenimiento de cuenta inactiva.
3. **Fondeo Cripto / Stablecoins (USDT / USDC):** Soporta ingresos de fondos mediante transferencias de stablecoins, evitando el costo de transferencias bancarias internacionales (SWIFT).
4. **Acciones Fraccionadas:** Permite comprar desde \$1 USD de cualquier acción de Wall Street.
5. **Entorno Paper Trading Nativo:** Incluye un simulador exacto con claves API reales antes de fondear dinero físico.

---

## 2. Paso a Paso para la Apertura de Cuenta (Residentes en Argentina)

### Paso 1: Registro Inicial
1. Ingresar en el navegador a **[https://alpaca.markets](https://alpaca.markets)**.
2. Hacer clic en **"Sign Up"** (esquina superior derecha).
3. Ingresar correo electrónico personal y contraseña segura.
4. Confirmar el correo electrónico haciendo clic en el enlace recibido.
5. En la selección de tipo de cuenta, elegir: **"Individual Trading Account"** (Cuenta Individual).

### Paso 2: Formulario de Identidad y Residencia (KYC)
Completar los campos con los datos reales tal como figuran en el documento de identidad:
- **Country of Residence (País de Residencia):** Seleccionar **Argentina**.
- **First Name / Last Name:** Nombres y Apellidos completos.
- **Date of Birth:** Fecha de nacimiento.
- **Tax Identification Number (TIN):** Ingresar tu número de **CUIL o CUIT** (sin guiones).
- **Employment Information:** Ocupación o actividad laboral actual.

### Paso 3: Documentación Requerida
Subir fotografías claras, sin sombras ni reflejos:
1. **Identificación Oficial:**
   - **DNI Argentino** (foto nítida del frente y del dorso) o **Pasaporte Argentino** vigente.
2. **Comprobante de Domicilio (Proof of Address):**
   - Factura de servicios (electricidad, gas, agua, internet, telefonía), resumen de tarjeta de crédito o extracto bancario a tu nombre.
   - Antigüedad menor a 3 meses.
   - La dirección debe coincidir exactamente con la ingresada en el formulario.

### Paso 4: Declaraciones Regulatorias (W-8BEN)
- Al ser residente argentino no estadounidense, el sistema genera digitalmente el formulario **W-8BEN** (tratado de no residencia en EE.UU.). Solo requiere firmar digitalmente con el mouse o teclado.
- El proceso de aprobación suele tardar entre **24 y 48 horas hábiles**.

---

## 3. Fondeo de la Cuenta (Cómo ingresar dinero desde Argentina)

### Opción Recomendada: Stablecoins (USDT o USDC)
1. En el panel de control de Alpaca (*Dashboard*), ir a la sección **"Banking"** o **"Funding"** $\rightarrow$ **"Deposit"**.
2. Seleccionar **"Crypto / Stablecoin Deposit"** (USDT o USDC).
3. La plataforma generará una dirección de billetera y red (ej: Ethereum ERC-20, Polygon o Solana según esté habilitado).
4. Enviar los USDT desde tu billetera o exchange (Binance, Bybit, Lemon, etc.).
5. Los fondos se acreditan directamente en dólares líquidos (**USD**) en tu balance de Alpaca.

---

## 4. Generación de Claves API (API Keys)

Una vez aprobada la cuenta:
1. En el panel izquierdo de Alpaca, seleccionar la pestaña **"API Keys"** (puedes alternar entre *Live Trading* y *Paper Trading*).
2. Hacer clic en el botón **"Generate New Keys"** o **"Create Key"**.
3. Se generarán dos claves:
   - **API Key ID:** Identificador público (ej: `PK...` o `AK...`).
   - **Secret Key:** Clave privada secreta (solo se muestra una vez; copiarla y guardarla en un lugar seguro).

---

## 5. Integración con el Bot `trading_ollama`

Para activar la conexión automática:
1. Guardar las claves en el archivo `.env` del proyecto en Linux:
   ```bash
   ALPACA_API_KEY="tu_api_key_id"
   ALPACA_SECRET_KEY="tu_secret_key"
   ALPACA_BASE_URL="https://api.alpaca.markets" # o https://paper-api.alpaca.markets para pruebas
   ```
2. Nuestro adaptador `backend/execution/alpaca_broker.py` tomará estas credenciales y ejecutará todas las órdenes del bot en tiempo real contra Wall Street y Cripto.
