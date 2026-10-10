# Architecture et choix techniques

## Principe

L'architecture en médaillon organise les données en couches de qualité croissante. On ne passe d'une couche à l'autre que par une transformation explicite et testée. Chaque couche peut être reconstruite à partir de la précédente, sans retélécharger la source.

```
data/raw  ──►  warehouse.duckdb (schémas bronze / silver / gold)  ──►  fichiers Parquet par couche
```

Le pipeline écrit dans **un seul fichier DuckDB** (`data/warehouse.duckdb`, trois schémas) *et* exporte chaque couche en Parquet. Le fichier DuckDB sert à interroger les données en SQL ; les Parquet sont portables (Power BI, Python, Spark...).

## Les trois couches

### Bronze : la source, sans y toucher
- Toutes les colonnes restent du **texte** (`all_varchar`) : aucune valeur ne peut être modifiée ou perdue silencieusement par une inférence de type.
- `_source_file` et `_ingested_at` assurent la traçabilité.
- Contrôle : volumes comparés à la version officielle du jeu (avertissement si différent, car l'utilisateur peut avoir une autre version).

### Silver : nettoyé, typé, dédoublonné
| Table | Règles |
|---|---|
| `customers`, `sellers` | texte normalisé (`lower/trim`, état en majuscules), une ligne par clé |
| `products` | colonnes mal orthographiées corrigées ; catégorie traduite en anglais ; manquante → `unknown` ; 2 traductions absentes ajoutées |
| `orders` | `TRY_CAST` des dates (une valeur invalide devient `NULL` au lieu de faire échouer le chargement) ; `delivery_days`, `delay_days` calculés **uniquement** pour les commandes livrées avec une chronologie cohérente ; `has_date_anomaly` signale une livraison avant l'achat |
| `order_items`, `payments` | typage, rejet des lignes sans montant |
| `reviews` | **un avis par commande**, le plus récent ; notes hors 1-5 rejetées |

### Gold : modèle métier
Schéma en étoile (voir [data_model.md](data_model.md)) et tables de KPI pré-calculées (`kpi_*`).

Deux notions structurent tous les KPI :
- **`is_valid_sale`** : commande avec au moins un article, ni annulée ni indisponible. Définie à un seul endroit (`sql/gold/04_fact_orders.sql`).
- **`is_late`** : `delay_days > 0`, comparaison **au jour près** (la date estimée est à minuit ; comparer les horodatages compterait en retard une commande livrée le jour prévu).

## Pourquoi ces choix

| Choix | Raison |
|---|---|
| **DuckDB** | Base SQL embarquée : aucune installation de serveur, lecture directe de CSV/Parquet, très rapide en agrégation. N'importe qui clone le dépôt et le pipeline tourne |
| **SQL pour les transformations** | Lisible par un analyste, portable vers BigQuery ou Snowflake avec peu d'adaptations |
| **Python léger** | Orchestration seulement : chaque étape est un module court, testable séparément |
| **Parquet entre les couches** | Format colonne typé et compressé, lu par tous les outils |
| **Contrôles bloquants** | Une erreur de données est détectée à la couche où elle apparaît, pas dans le dashboard |
| **Dashboard sans librairie** | Aucune dépendance à maintenir, fonctionne hors ligne, et la logique de calcul se teste sous Node |

## Contrôles qualité (`pipeline/quality.py`)

Statuts : `pass`, `warn` (problème connu de la source, documenté, non bloquant), `fail` (arrête le pipeline).

- **Silver** : clés uniques, colonnes obligatoires, 6 relations d'intégrité référentielle, plages de valeurs, réconciliation Bronze/Silver.
- **Gold** : même nombre de lignes que Silver, CA identique entre `order_items` et `fact_orders`, **CA de chaque table KPI = CA global**, cohérence des dimensions.
- Le rapport est écrit dans `outputs/quality_report.json`.

## Du Gold au dashboard

`pipeline/dashboard_export.py` écrit `dashboard/data.js` : deux tables en colonnes (une ligne par commande valide, une ligne par article vendu). Le navigateur recalcule tous les indicateurs à partir de ces tables, ce qui permet des filtres exacts, y compris pour les comptages distincts (clients, commandes par catégorie) qu'une table pré-agrégée ne saurait pas recombiner.

Le test `tests/dashboard_logic.test.js` vérifie que ces calculs reproduisent les tables Gold (`outputs/kpi_*.csv`) sans écart.

## Ajouter une étape ou un KPI

1. Ajouter un fichier `sql/gold/13_mon_kpi.sql` (`CREATE OR REPLACE TABLE gold.kpi_xxx AS ...`) : il est exécuté automatiquement, dans l'ordre alphabétique.
2. Si le nom commence par `kpi_`, un CSV est généré dans `outputs/`.
3. Ajouter un contrôle de réconciliation dans `gold_checks()` et un test dans `tests/test_pipeline.py`.
