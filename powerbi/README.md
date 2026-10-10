# Construire le rapport dans Power BI Desktop

Le pipeline exporte le modèle en étoile Gold en CSV dans `outputs/powerbi/` (dossier non versionné, généré par `python run_pipeline.py`). Power BI Desktop fonctionne uniquement sous Windows.

> Les mesures de [`measures.dax`](measures.dax) suivent les mêmes définitions que le pipeline, mais elles n'ont **pas été exécutées dans Power BI** lors de la création du projet. Les valeurs de contrôle ci-dessous permettent de les vérifier en 2 minutes.

## 1. Importer les tables

*Accueil → Obtenir des données → Texte/CSV*, puis charger ces 6 fichiers de `outputs/powerbi/` :

`fact_orders.csv`, `fact_order_items.csv`, `dim_customers.csv`, `dim_products.csv`, `dim_sellers.csv`, `dim_date.csv`

(Alternative : *Obtenir des données → Parquet* sur `data/gold/`.) Vérifier les types dans Power Query : `date` en Date, les colonnes `is_*` en Vrai/Faux, les montants en Nombre décimal.

## 2. Relations (vue Modèle)

| De (plusieurs) | Vers (un) | Sens du filtre |
|---|---|---|
| `fact_orders[purchase_date_key]` | `dim_date[date_key]` | unique |
| `fact_orders[customer_unique_id]` | `dim_customers[customer_unique_id]` | unique |
| `fact_order_items[order_id]` | `fact_orders[order_id]` | unique |
| `fact_order_items[product_id]` | `dim_products[product_id]` | unique |
| `fact_order_items[seller_id]` | `dim_sellers[seller_id]` | unique |

Puis : *clic droit sur `dim_date` → Marquer comme table de dates* (colonne `date`).

## 3. Mesures

Créer une table de mesures et coller le contenu de [`measures.dax`](measures.dax).

## 4. Valeurs de contrôle (période complète, sans filtre)

| Mesure | Valeur attendue |
|---|---|
| Revenue | 13 494 401 |
| Orders | 98 199 |
| Customers | 94 983 |
| Repeat Rate | 3,04 % |
| Avg Delivery Days | 12,50 |
| Late Rate | 6,77 % |
| Avg Review Score | 4,10 |

Si un écart apparaît, vérifier d'abord le type des colonnes booléennes et les relations.

## 5. Pages suggérées

- **Vue d'ensemble** : cartes (Revenue, Orders, Average Order Value, Customers), courbe `Revenue` par `dim_date[year_month]`, histogramme par `dim_products[category]`.
- **Livraison et satisfaction** : `Avg Review Score` par tranche de retard (colonne calculée sur `fact_orders[delay_days]`), `Late Rate` par `customer_state`.
- **Segments** : `Repeat Rate` par État, `Revenue` par `main_payment_type`.
