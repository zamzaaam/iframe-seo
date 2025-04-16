import pandas as pd
from typing import List, Dict, Optional
import json
from ..utils import extract_id_and_code

class IframeAnalyzer:
    def __init__(self):
        self.template_mapping = self._load_template_mapping()

    def _load_template_mapping(self):
        """Charge le fichier JSON de mapping des templates"""
        try:
            with open("data/template_mapping.json", "r") as f:
                return json.load(f)
        except Exception:
            return None

    def get_template_name(self, form_id: str) -> Optional[str]:
        """Récupère le nom du template pour un ID donné"""
        if not form_id or not self.template_mapping:
            return None
        return self.template_mapping.get(form_id)

    def analyze_crm_data(self, results: List[Dict], mapping_data: Optional[pd.DataFrame] = None, 
                        mapping_config: Optional[Dict] = None) -> pd.DataFrame:
        """
        Analyse les données CRM et applique le mapping personnalisé
        
        Args:
            results: Résultats d'extraction d'iframes
            mapping_data: DataFrame contenant les données de mapping externes
            mapping_config: Configuration du mapping avec:
                - url_column: Nom de la colonne contenant les URLs dans mapping_data
                - id_column: Nom de la colonne contenant les IDs dans mapping_data
                - selected_columns: Liste des colonnes additionnelles à inclure
        """
        df = pd.DataFrame(results)
        
        # Extraction basique des codes CRM
        df['CRM Campaign'] = df['Iframe'].apply(
            lambda x: extract_id_and_code(x)[1])

        if mapping_data is not None and mapping_config is not None:
            # Création d'une clé de mapping unique (URL + Form ID)
            df['mapping_key'] = df['URL source'] + '|' + df['Form ID']
            mapping_data['mapping_key'] = (
                mapping_data[mapping_config['url_column']] + '|' + 
                mapping_data[mapping_config['id_column']]
            )

            # Sélection des colonnes à fusionner
            columns_to_merge = ['mapping_key'] + mapping_config['selected_columns']
            mapping_subset = mapping_data[columns_to_merge]

            # Fusion des données
            df = df.merge(
                mapping_subset,
                on='mapping_key',
                how='left'
            )

            # Nettoyage
            df = df.drop('mapping_key', axis=1)

        return df