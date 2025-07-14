# Documentación de APIs - Mitosis

## Resumen de APIs Integradas

Este documento describe todas las APIs y servicios externos utilizados en la aplicación Mitosis.

### APIs Integradas y Funcionando ✅

#### 1. **Tavily API** - Búsqueda Web
- **Propósito**: Búsqueda web avanzada con resultados enriquecidos
- **Estado**: ✅ Integrado y funcionando
- **Clave**: `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`
- **Ubicación**: `/app/backend/.env`
- **Archivos**:
  - `src/tools/tavily_search_tool.py`
  - `src/tools/enhanced_web_search_tool.py`
- **Uso**: WebSearch desde la página de bienvenida

#### 2. **MongoDB** - Base de Datos
- **Propósito**: Persistencia de datos, tareas, conversaciones y archivos
- **Estado**: ✅ Integrado y funcionando
- **URL**: `mongodb://localhost:27017/task_manager`
- **Ubicación**: `/app/backend/.env`
- **Archivos**:
  - `src/services/database.py`
- **Uso**: Almacenamiento de todas las operaciones

#### 3. **Firecrawl API** - Web Scraping Avanzado
- **Propósito**: Scraping web más sofisticado que BeautifulSoup
- **Estado**: ✅ Integrado y configurado
- **Clave**: `fc-d7697dffe9a04c4e973e213284e9de76`
- **Ubicación**: `/app/backend/.env`
- **Archivos**:
  - `src/tools/firecrawl_tool.py`
- **Funcionalidades**:
  - Extracción de contenido estructurado
  - Manejo de JavaScript y SPAs
  - Soporte para múltiples formatos de salida
  - Crawling de múltiples páginas

#### 4. **QStash (Redis)** - Jobs en Background
- **Propósito**: Procesamiento de trabajos en segundo plano
- **Estado**: ✅ Integrado y configurado
- **URL**: `redis://default:AeJLAAIjcDE4NmM1NWI5ZjQwYjE0NDIwYjRhNWZmNDhmOTk2OGU1MHAxMA@normal-vervet-57931.upstash.io:6379`
- **Ubicación**: `/app/backend/.env`
- **Archivos**:
  - `src/tools/qstash_tool.py`
- **Funcionalidades**:
  - Creación y gestión de trabajos
  - Monitoreo de progreso
  - Colas de prioridad
  - Timeout y cancelación

#### 5. **Playwright** - Automatización de Navegadores
- **Propósito**: Automatización web y scraping avanzado
- **Estado**: ✅ Integrado y configurado
- **Dependencias**: `playwright>=1.40.0`
- **Ubicación**: `/app/backend/requirements.txt`
- **Archivos**:
  - `src/tools/playwright_tool.py`
- **Funcionalidades**:
  - Navegación automatizada
  - Capturas de pantalla
  - Extracción de contenido dinámico
  - Interacción con formularios
  - Ejecución de JavaScript

### APIs Disponibles (No Integradas) 🔄

#### 6. **RapidAPI** - APIs Externas
- **Propósito**: Acceso a múltiples APIs de terceros
- **Estado**: 🔄 Clave disponible, pendiente de uso específico
- **Clave**: `e3c8f40077msh2383361adacc215p1fb470jsn0a2150f802f9`
- **Recomendación**: Solo integrar si se necesitan APIs específicas

#### 7. **Smithery** - Agentes Personalizados
- **Propósito**: Desarrollo de agentes especializados
- **Estado**: 🔄 Clave disponible, pendiente de investigación
- **Clave**: `generous-zebra-3J27EB`
- **Recomendación**: Investigar capacidades antes de integrar

### Funcionalidades Ya Implementadas (No Necesitan APIs Externas)

#### ❌ **NO INTEGRAR** - Ya tenemos implementado:

1. **Búsqueda Web Básica**: Ya tenemos Tavily + DuckDuckGo
2. **Gestión de Archivos**: Ya implementado en file_manager_tool.py
3. **Comandos Shell**: Ya implementado en shell_tool.py
4. **Web Scraping Básico**: Ya tenemos BeautifulSoup
5. **Base de Datos**: Ya tenemos MongoDB
6. **Sistema de Tareas**: Ya implementado en frontend
7. **Chat Interface**: Ya implementado

### Integraciones Recomendadas

#### 🎯 **Prioridad Alta**:
1. **Firecrawl** - Mejora significativa en scraping
2. **QStash** - Mejora UX para tareas largas
3. **Playwright** - Automatización web avanzada

#### 🔍 **Prioridad Media**:
1. **Smithery** - Después de investigar capacidades
2. **RapidAPI** - Solo APIs específicas necesarias

### Estructura de Archivos para Nuevas Integraciones

```
/app/backend/src/tools/
├── firecrawl_tool.py         # 🔄 Por crear
├── qstash_tool.py            # 🔄 Por crear
├── playwright_tool.py        # 🔄 Por crear
├── rapidapi_tool.py          # 🔄 Por crear (opcional)
└── smithery_tool.py          # 🔄 Por crear (opcional)
```

### Variables de Entorno Necesarias

```bash
# /app/backend/.env
# Existentes
TAVILY_API_KEY=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
MONGO_URL=mongodb://localhost:27017/task_manager

# Nuevas por agregar
FIRECRAWL_API_KEY=fc-d7697dffe9a04c4e973e213284e9de76
QSTASH_URL=redis://default:AeJLAAIjcDE4NmM1NWI5ZjQwYjE0NDIwYjRhNWZmNDhmOTk2OGU1MHAxMA@normal-vervet-57931.upstash.io:6379
RAPIDAPI_KEY=e3c8f40077msh2383361adacc215p1fb470jsn0a2150f802f9
SMITHERY_KEY=generous-zebra-3J27EB
```

### Estado de Servicios

| Servicio | Estado | Funcionalidad | Mejora |
|----------|--------|---------------|---------|
| Tavily | ✅ Activo | Búsqueda web | - |
| MongoDB | ✅ Activo | Base de datos | - |
| Firecrawl | 🔄 Pendiente | Web scraping | +++ |
| QStash | 🔄 Pendiente | Jobs background | +++ |
| Playwright | 🔄 Pendiente | Automatización | ++ |
| RapidAPI | 🔄 Pendiente | APIs externas | + |
| Smithery | 🔄 Pendiente | Agentes custom | ? |

### Notas de Implementación

1. **Principio de Valor**: Solo integrar APIs que agreguen valor real
2. **Evitar Duplicación**: No integrar si ya tenemos funcionalidad equivalente
3. **Priorizar UX**: Priorizar integraciones que mejoren experiencia de usuario
4. **Documentar Todo**: Cada nueva integración debe documentarse aquí

---

**Última actualización**: 2025-01-15
**Responsable**: Mitosis Development Team