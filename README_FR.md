<p align="center">
  <a href="README_EN.md">English</a> |
  <a href="README.md">简体中文</a> |
  <a href="README_ZHT.md">繁體中文</a> |
  <a href="README_JA.md">日本語</a> |
  <a href="README_KO.md">한국어</a> |
  <a href="README_FR.md">Français</a>
</p>

# AgentMemory v0.3

> **Système de Mémoire à Double Piste + Bibliothèque** — Infrastructure de mémoire persistante, portable et hot-swap pour agents IA

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)

---

## Philosophie de Conception : La Mémoire comme une Bibliothèque

> **Le livre lui-même ne change pas, mais le système de catalogage rend la recherche précise.**

Les systèmes de mémoire traditionnels sont confrontés à une contradiction fondamentale : **la recherche sémantique (correspondance floue) et la classification exacte (filtrage par domaine) sont mutuellement exclusives.**

La réponse d'AgentMemory : **Les deux pistes coexistent. Jamais de compromis.**

La même mémoire existe simultanément sur deux pistes :

```
Même mémoire :
├─ Piste de classification bibliothèque (.md contenu + .meta.json métadonnées) → recherche exacte, limites de gestion
└─ Piste de vecteurs Embedding (.vec.json) → recherche sémantique, correspondance floue
```

**Garantie de granularité** : minimum 3 couches de classification (bibliothèque / étagère / livre — garantissant une classification précise de chaque mémoire), maximum illimité, profondeur dynamique.

---

## Vue d'Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Application hôte (Agent / CLI / Web API) │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  MemoryManager (API async unifiée)                            │
│  add() / get() / delete() / search() / list() / compress()  │
└────────────────────────────┬─────────────────────────────────┘
                             │
          ┌──────────────────┴──────────────────┐
          ▼                                      ▼
┌─────────────────────┐              ┌─────────────────────────┐
│   L4FilesStore      │              │   L3LanceDBStore        │
│   (Persistance Fichier)              │   (Recherche vectorielle)│
│                     │              │                         │
│  memory/<id>.md     │◄──── sync ──►│  LanceDB Table         │
│  memory/<id>.meta   │              │  (Similarité sémantique)│
│  memory/<id>.vec.json              │                         │
└─────────────────────┘              └─────────────────────────┘
          │                                      │
          ▼ (en lecture)                          │
┌─────────────────────┐              ┌─────────────────────────┐
│   L1LCMCompressor   │              │   Recherche hybride BM25│
│   (Compression ctx)  │              │   (Python pur, 0 déps)  │
│                     │              │                         │
│  Entité → Résumé    │              │  k1=1.2, b=0.75         │
│  → Injection AI ctx │              │  α=0.7 (vector/BM25)   │
└─────────────────────┘              └─────────────────────────┘
```

### Responsabilités des 3 couches

| Couche | Composant | Responsabilité |
|--------|-----------|----------------|
| **L4** | `L4FilesStore` | `.md` contenu + `.meta.json` métadonnées + `.vec.json` vecteurs, persistance système de fichiers |
| **L3** | `L3LanceDBStore` | Recherche vectorielle LanceDB (bascule automatique vers JSON + numpy pur si indisponible), recherche hybride BM25 |
| **L1** | `L1LCMCompressor` | Compression mémoire en résumé + liste d'entités, utilisée pour l'injection dans les prompts IA, amélioration de la pertinence par query |
| **L3** | `SyncManager` | Synchronisation double piste L4 ↔ L3, détection auto mots-clés sync, verrouillage fichier portalocker |
| **L3** | `LibraryClassifier` | Classification automatique 5 catégories de premier niveau, scoring normalisé par mots-clés, tokenisation mise en cache |
| **L3** | `IntegrityVerifier` | Signature d'intégrité fichier HMAC-SHA256, détection de falsification |

### Recherche à Double Piste

| Piste | Méthode | Optimal pour |
|-------|---------|-------------|
| **Piste 1** | Classification bibliothèque (category_path / tags) | Recherche exacte, filtrage par domaine |
| **Piste 2** | Vecteurs Embedding (similarité sémantique) | Recherche floue, associations sémantiques |

### Règles de Classification Bibliothèque

Minimum 3 couches (bibliothèque / étagère / livre — garantissant la granularité), maximum illimité, profondeur dynamique :

```
Projet/Shiliuzi/Corpus/EntraînementNLLB                 ✅ Minimum 3 couches
Projet/Shiliuzi/Corpus/EntraînementNLLB/2026-06           ✅ Extension illimitée
Apprentissage/AI/Transformer                                ✅ 3 couches
AI/Agent/SystèmeMémoire/VCP                      ✅ 4 couches
```

---

## Composants Principaux

| Composant | Fichier | Description |
|-----------|---------|-------------|
| `MemoryManager` | `manager.py` | API async unifiée : add/get/delete/search/list/compress |
| `L4FilesStore` | `l4_files.py` | Stockage triple fichier md + meta.json + vec.json, verrouillage fichier portalocker |
| `L3LanceDBStore` | `l3_lancedb.py` | Recherche vectorielle LanceDB + JSON Fallback + Recherche hybride BM25 |
| `L1LCMCompressor` | `l1_lcm.py` | Compression contexte, extraction d'entités FactType, amélioration pertinence query |
| `SyncManager` | `sync.py` | Synchronisation double piste L4 ↔ L3, détection auto mots-clés sync |
| `LibraryClassifier` | `library.py` | Classification par mots-clés 5 catégories, validation chemin hiérarchique, tokenisation mise en cache |
| `Embedder` | `embedder.py` | HashEmbedder (0 déps) / DashScopeEmbedder (API OpenAI-Compatible) |
| `IntegrityVerifier` | `integrity.py` | Vérification signature HMAC-SHA256 |

---

## Structure de Données

Chaque mémoire = 3 fichiers dans le même répertoire :

```
memory/
├── abc123.md           # Contenu lisible
├── abc123.meta.json   # Métadonnées
└── abc123.vec.json    # Données vectorielles (une par mémoire, co-localisées avec .md)
```

### Format meta.json

```json
{
  "id": "abc123...",
  "created_at": "2026-06-07T00:00:00",
  "updated_at": "2026-06-07T00:00:00",
  "category_path": "Project/Shiliuzi/Training",
  "tags": ["nllb", "success"],
  "source": "manual",
  "importance": 0.8,
  "trust_score": 1.0,
  "flagged": false,
  "signed_at": 1759804800.123
}
```

---

## Détails d'Implémentation : Les Petites Astuces Qui Rendent le Code Élégant

### Écritures Atomiques : tempfile + os.replace (Compatible Windows)

Les écritures L4 utilisent une opération atomique en deux étapes :

```python
# 1. Écrire dans fichier temporaire
tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp", dir=base_dir)
tmp.write(content); tmp.close()
# 2. os.replace remplacement atomique (garanti atomique aussi sur Windows)
os.replace(tmp.name, target_path)
```

os.rename ne fonctionne pas cross-drive sur Windows. os.replace le peut. C'est un angle mort pour beaucoup de projets Python cross-platform.

### portalocker : Verrouillage Fichier Cross-Platform

```python
with _portalocker_lock(lock_path):
    # Les opérations d'écriture sont automatiquement verrouillées
    ...
```

`portalocker` prioritaire, avec fallback Windows `msvcrt` et Unix `fcntl`. Les lectures utilisent des verrous partagés ; les écritures utilisent des verrous exclusifs. Le pattern `contextmanager` garantit la libération du verrou même en cas d'exception.

### Pattern `_embed_fn` : Interface Unifiée Sync/Async

`embed()` de DashScopeEmbedder est `async def` ; celui de HashEmbedder est `def`. Les appelants utilisent une interface unifiée :

```python
# Dans SyncManager.__init__ :
if hasattr(embedder, 'embed_sync'):
    self._embed_fn = embedder.embed_sync
else:
    self._embed_fn = embedder.embed
```

Détection runtime — pas besoin de vérification de type. La classe de base Embedder fournit la propriété `embed_sync` ; les implémentations async wrappent dans un thread worker.

### Tokenisation Mise en Cache (LibraryClassifier)

Retokeniser à chaque correspondance de mot-clé est du gaspillage. `_tokenize()` utilise `@functools.lru_cache(maxsize=512)` :

```python
@functools.lru_cache(maxsize=512)
def _tokenize(self, text: str) -> tuple[str, ...]:
    ...
    return tuple(tokens)  # tuple est hachable, adapté comme clé lru_cache
```

Retourne `tuple` et non `list` — tuple est hachable et cachable.

### Normalisation des Scores : sqrt(keyword_count) Empêche les Grandes Catégories d'Écraser les Petites

La catégorie « Projet » a 20+ mots-clés ; « Préférences » n'en a que 8. Une somme brute laisserait toujours gagner la grande catégorie :

```python
scores[category] = cat_raw / (len(keywords) ** 0.5)  # normalisation sqrt
```

Utiliser `sqrt` au lieu de diviser directement par `len(keywords)` : les grandes listes aident, mais ne dominent pas.

### Normalisation Unicode + Détection Double Piste (injection.py)

Détecter les attaques par obfusquation nécessite deux étapes :

```python
texts_to_check = [text, _normalize_text(text)]  # Texte original + normalisé
```

Étapes de normalisation : gestion des caractères zero-width, décodage entités HTML, conversion fullwidth→halfwidth, décodage séquences Unicode escape, restauration mots backslash, suppression caractères contrôle BIDI. Les attaques par obfusquation (`rm\u200b-rf`, `rm&#x72;f`) sont exposées après normalisation.

### Paramètres BM25 Configurables

`k1` (saturation fréquence terme) et `b` (normalisation longueur document) de BM25 sont ajustables :

```python
# k1=1.2, b=0.75 sont les valeurs par défaut Lucene
l3_store.search_bm25(query, top_k=5, k1=1.2, b=0.75)
```

### Pondération Hybride α Ajustable

La pondération hybride entre similarité vectorielle et BM25 α par défaut 0.7 (vecteur 70%, BM25 30%) :

```python
alpha = 0.7
final_score = alpha * vec_score + (1 - alpha) * bm25_score
```

### Cache Stats 5 Minutes

`MemoryManager.stats()` a un cache local pour éviter de lire le système de fichiers à chaque appel :

```python
age = (datetime.now() - self._stats_timestamp).total_seconds()
if age < 300:  # Dans les 5 min, retourner le cache
    return self._stats_cache
```

### Persistance `access_count` (Pas une Variable Mémoire)

Beaucoup de systèmes de mémoire stockent les compteurs d'accès en mémoire — perdus au redémarrage. AgentMemory écrit `access_count` dans `.meta.json`, incrémentant et persistant à chaque appel `load_existing()`.

### Le Paramètre query Renforce l'Ordre de Pertinence de la Compression L1

`compress_for_context(memory_ids, query="...")` accepte un paramètre query ; les mémoires partageant des mots-clés avec la query sont classées plus haut dans le même niveau d'importance :

```python
def _relevance_score(mem):
    if not query_toks: return 0
    return sum(1 for tok in query_toks if tok in mem.get("content","").lower())
```

---

## Sécurité (Niveau P0)

| Protection | Emplacement | Description |
|------------|-------------|-------------|
| **Détection d'Injection** | `utils/injection.py` | Normalisation Unicode + détection double piste (original/normalisé tous vérifiés), 50+ patterns d'attaque incluant JNDI/SSTI/Shellshock/Prompt Injection |
| **trust_score** | `sync.py` | < 0.2 rejette l'écriture L3, ≤ 0.35 marque flagged + avertit |
| **Vérification HMAC** | `integrity.py` | Signature HMAC-SHA256, écriture `signed_at` dans `.meta.json` |
| **Validation API Key** | `embedder.py` | `DashScopeEmbedder.__init__` valide immédiatement, lève RuntimeError si absent |
| **Protection Injection LanceDB** | `web.py` / `cli.py` | Les guillemets simples dans category_path sont échappés en `''` (standard SQL) |
| **Écritures Atomiques** | `l4_files.py` | tempfile + os.replace — pas de fichiers temporaires même en cas de crash |
| **Verrouillage Fichier** | `l4_files.py` | Verrou exclusif portalocker, opérations d'écriture mutuellement exclusives |

---

## Sécurité Concurrence

La sécurité d'écriture est garantie par `portalocker` : Windows fallback msvcrt, Unix fallback fcntl :

```python
# L4FilesStore écriture : verrou exclusif automatique
with _portalocker_lock(lock_path):
    ...

# Lecture : verrou partagé automatique
with _file_lock(lock_path, exclusive=False):
    ...
```

---

## Installation

```bash
cd AgentMemory
pip install -e .
```

### Dépendances

**Dépendances runtime (seulement 3, aucun service externe nécessaire) :**

```
httpx>=0.25.0    # Appels HTTP async pour API
aiofiles>=23.0.0 # I/O fichier async
pydantic>=2.5    # Validation données (requis runtime)
```

**Dépendances optionnelles :**

```bash
pip install agentmemory[web]     # Support API Web (FastAPI + uvicorn)
pip install agentmemory[lancedb] # Base de données vectorielle LanceDB (scénarios haute performance)
pip install agentmemory[dev]     # Dépendances développement (pytest etc.)
```

> Quand LanceDB est indisponible (non installé), le système bascule automatiquement vers JSON pur + numpy — zéro dépendance supplémentaire pour fonctionner.

### Sélection Embedder

```python
from agent_memory import MemoryManager, get_embedder

# Par défaut (mode auto) : pas d'API Key → HashEmbedder (0 déps, fonctionne offline)
#                          a API Key → Embedding OpenAI-Compatible (n'importe quel provider compatible)
mm = MemoryManager()

# Explicite (lève RuntimeError immédiatement si pas d'API Key — pas de dégradation silencieuse)
mm = MemoryManager(embedder=get_embedder(backend="openai-compat"))

# Équivalent au mode auto par défaut
mm = MemoryManager(embedder=get_embedder())
```

> **Aucun lock-in modèle** : utilise le format API OpenAI-Compatible en interne ; détecte automatiquement n'importe quel provider supportant `/v1/embeddings` (DashScope / Minimax / OpenAI / serveur Embedding local, etc.).

### Variables d'Environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `AGENT_MEMORY_DIR` | `memory` | Répertoire de stockage mémoire |
| `AGENT_MEMORY_DATA_DIR` | `data` | Répertoire données vectorielles (table LanceDB / JSON Fallback) |
| `EMBEDDING_API_KEY` | - | API OpenAI-Compatible (recommandé ; fonctionne avec n'importe quel provider compatible) |
| `DASHSCOPE_API_KEY` | - | Compatibilité arrière, choisir avec `EMBEDDING_API_KEY` |
| `OPENAI_API_KEY` | - | Compatibilité arrière |

---

## Démarrage Rapide

### API Python

```python
import asyncio
from agent_memory import MemoryManager

async def main():
    mm = MemoryManager()

    # Ajouter une mémoire
    mem_id = await mm.add(
        content="Entraînement NLLB terminé avec succès, précision vocabulaire 85%",
        category_path="Project/Shiliuzi/Training",
        tags=["nllb", "success", "training"],
        importance=0.9
    )
    print(f"Added: {mem_id}")

    # Recherche sémantique (mode vecteur par défaut)
    results = await mm.search("Entraînement modèle NLLB")
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:60]}")

    # Lister par catégorie
    all_memories = await mm.list(category_path="Project/Shiliuzi")
    print(f"Found {len(all_memories)} memories")

    # Stats
    stats = await mm.stats()
    print(f"Total: {stats['total_memories']}, Categories: {stats['categories']}")

    # Compression L1 (injecter dans AI Context)
    # paramètre query : les mémoires pertinentes pour la query sont priorisées
    compressed = await mm.compress_for_context([mem_id], query="Entraînement NLLB")
    print(compressed)

    # Supprimer
    await mm.delete(mem_id)

asyncio.run(main())
```

### CLI

```bash
# Ajouter mémoire (classification auto)
python -m agent_memory.cli add "Mémoire test"

# Spécifier catégorie et tags
python -m agent_memory.cli add "Entraînement NLLB terminé" --category "Project/Shiliuzi/Training" --tags "nllb,done"

# Recherche sémantique (défaut)
python -m agent_memory.cli search "Entraînement modèle NLLB"

# Recherche par mot-clé (BM25, pas de modèle vectoriel nécessaire)
python -m agent_memory.cli search "NLLB" --mode bm25

# Recherche hybride (vecteur + BM25 pondéré)
python -m agent_memory.cli search "NLLB" --mode hybrid

# Lister tout
python -m agent_memory.cli list

# Lister par catégorie
python -m agent_memory.cli list --category "Project/Shiliuzi"

# Afficher une mémoire
python -m agent_memory.cli show <memory_id>

# Stats
python -m agent_memory.cli stats

# Supprimer
python -m agent_memory.cli delete <memory_id>

# Afficher toutes les catégories de premier niveau
python -m agent_memory.cli category --show-all

# Afficher tous les chemins de catégorie utilisés
python -m agent_memory.cli category --list

# Signature HMAC (nécessaire pour les nouveaux dossiers)
python -m agent_memory.cli sign memory/ --key "your-secret-key-here"

# Vérification HMAC (vérifier intégrité du dossier)
python -m agent_memory.cli verify memory/ --key "your-secret-key-here"

# Ré-embedding (lors du changement d'embederder)
python -m agent_memory.cli --json reembed --embedder hash

# Démarrer serveur API Web
python -m agent_memory.cli serve --port 8765
```

### API MemoryManager

| Méthode | Retourne | Description |
|---------|----------|-------------|
| `add(content, category_path, tags, importance)` | `str` (memory_id) | Ajouter mémoire, écriture double piste L4 + L3 |
| `get(memory_id)` | `dict \| None` | Obtenir par ID |
| `delete(memory_id)` | `bool` | Supprimer de L4 + L3 + vec.json simultanément |
| `search(query, limit, category_path, mode)` | `list[dict]` | Recherche vecteur/BM25/hybride, mode=vector/bm25/hybrid |
| `list(category_path, limit)` | `list[dict]` | Lister par catégorie |
| `compress_for_context(memory_ids, query)` | `str` | Compression L1 ; paramètre query renforce la priorité des mémoires pertinentes |
| `stats()` | `dict` | Stats (cache 5 min) : total/catégories/taille stockage/couverture L3 |

---

## Arrière-plan Transparent (Capture Automatique de Mémoire)

Sans déclencheur — TransparentBackground fonctionne automatiquement :

- **Capture par battement de cœur** : Stocke automatiquement les fragments de conversation toutes les N minutes
- **Résumé périodique** : Génère automatiquement un résumé de session tous les 20 tours (stocké dans « Session/Résumé périodique »)
- **Préchargement de contexte** : Injecte automatiquement les mémoires pertinentes dans le contexte AI avant de répondre

### CLI

```bash
# Exécution continue (battement de cœur toutes les 5 minutes)
agentmemory bg --agent-id main

# Déclenchement unique (pour cron)
agentmemory bg --agent-id main --once
```

### Exemple de configuration OpenClaw (mémoire automatique toutes les 5 minutes)

```json
{
  "name": "memory-heartbeat",
  "sessionTarget": "isolated",
  "schedule": { "kind": "cron", "expr": "*/5 * * * *", "tz": "Asia/Shanghai" },
  "payload": { "kind": "agentTurn", "message": "agentmemory bg --agent-id main --once" }
}
```

### API Python

```python
from src.adapters.transparent_background import TransparentBackground

tb = TransparentBackground(agent_id="main")

# Précharger les mémoires pertinentes avant de répondre
context = await tb.inject_context_for_prompt(
    current_message="Quelle est l'avancement de la compétition provinciale ?",
    max_memories=5,
    max_chars=2000
)
# → "\n\n[Mémoires pertinentes]\n- [石榴籽/Projet] La date limite du projet est 2026-06-15...\n[/Mémoires pertinentes]"
```

---

## Serveur MCP (Invocation d'Outils Multi-Plateforme)

Expose les outils de mémoire via MCP (Model Context Protocol), supportant tous les outils de codage AI majeurs :

| Client | Protocole | Configuration |
|--------|-----------|---------------|
| Claude Code | MCP stdio | `~/.claude/settings.json` |
| Codex | MCP stdio | `~/.config/codex/config.json` |
| Cursor | MCP stdio/HTTP | Settings → MCP |
| Windsurf | MCP stdio/HTTP | Settings → MCP |

### Démarrer le serveur MCP

```bash
# Claude Code / Codex (mode stdio)
agentmemory mcp

# Autres clients (mode HTTP)
agentmemory mcp --http --port 8765
```

### Configuration Claude Code

Ajouter dans `~/.claude/settings.json` :

```json
{
  "mcpServers": {
    "agentmemory": {
      "command": "agentmemory",
      "args": ["mcp"]
    }
  }
}
```

### Outils MCP

| Outil | Description |
|-------|-------------|
| `memory_add` | Ajouter une mémoire |
| `memory_search` | Recherche sémantique/mots-clés/hybride |
| `memory_list` | Lister par catégorie |
| `memory_get` | Obtenir une seule mémoire |
| `memory_delete` | Supprimer une mémoire |
| `memory_stats` | Statistiques |
| `memory_compress` | Compression de contexte L1 |

### Exemples d'utilisation

```
# Mémoriser une information importante
Remember: memory_add content="Compétition provinciale 石榴籽 2026-06-15" importance=0.9 tags="石榴籽"

# Rechercher des mémoires pertinentes
Search: memory_search query="date compétition" limit=5 mode="hybrid"
```

---

## Comparaison avec Autres Systèmes

| Système | Format Données | Indexation | Multi-Agent | Support NAS | Zéro Dépendance Externe |
|---------|---------------|-----------|-------------|-------------|------------------------|
| Hermes | Fichiers | Pas de vecteurs | Espace de travail partagé | Natif | ✅ |
| VCP | Fichiers + vecteurs | Tag + vecteur | Dossier partagé | SQLite fichier unique | ✅ |
| Mem0 | Vecteurs + graphe | Vecteur + relations | Multi-tenant | Nécessite DB | ❌ |
| Letta | Memory Blocks | Index par bloc | Mémoire Agent | Nécessite service | ❌ |
| **AgentMemory v0.3** | md + vec.json | Recherche double piste | Dossier partagé | Natif | ✅ |

---

## Enregistrements de Décisions d'Architecture (v0.3)

| Décision | Description | Raison |
|----------|-------------|--------|
| Suppression L2 Graph-DB | 3 → 4 couches | Graph-DB surdimensionné ; les chemins de classification suffisent |
| Suppression mécanisme transition phase | Fichiers + vecteurs toujours double piste | Vérification VCP : transition de phase non nécessaire |
| Contrôle écriture concurrente | Verrous fichier portalocker | Scénarios d'écriture concurrente multi-Agent |
| Embedder par défaut Hash | Zéro dépendance, déterministe | 生非异也，善假于物也 |
| LanceDB prioritaire + JSON Fallback | Bascule auto si LanceDB indisponible | LanceDB pour haute performance, JSON pour zéro dépendance |
| Recherche hybride BM25 | Implémentation Python pur, zéro déps supplémentaire | Complément recherche par mot-clé pur, sans modèle vectoriel |
| min_depth=3 | Structure 3 niveaux bibliothèque/étagère/livre | Garantit granularité mémoire ; empêche le niveau supérieur d'être trop vague |

---

## Licence

MIT License — libre d'utilisation, modification et distribution.

---

_AgentMemory — La Mémoire comme une Bibliothèque. Double piste coexiste. Jamais de compromis._
