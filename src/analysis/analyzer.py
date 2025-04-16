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
        """
        df = pd.DataFrame(results)
        
        # Extraction basique des codes CRM de l'URL
        df['CRM Campaign (URL)'] = df['Iframe'].apply(
            lambda x: extract_id_and_code(x)[1])

        if mapping_data is not None and mapping_config is not None:
            # Création d'une clé de mapping unique
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

            # Supposons que la colonne CRM du mapping s'appelle 'CRM Campaign'
            if 'CRM Campaign' in mapping_config['selected_columns']:
                # Créer la colonne finale en priorisant l'URL puis le mapping
                df['Final CRM Campaign'] = df['CRM Campaign (URL)'].combine_first(df['CRM Campaign'])
                
                # Supprimer les colonnes intermédiaires
                df = df.drop(['CRM Campaign (URL)', 'CRM Campaign'], axis=1)
                
                # Renommer la colonne finale
                df = df.rename(columns={'Final CRM Campaign': 'CRM Campaign'})

            # Nettoyage
            df = df.drop('mapping_key', axis=1)

        else:
            # Si pas de mapping, renommer simplement la colonne URL
            df = df.rename(columns={'CRM Campaign (URL)': 'CRM Campaign'})

        return df