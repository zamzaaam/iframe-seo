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
                        selected_columns: Optional[List[str]] = None, id_column: str = 'ID') -> pd.DataFrame:
        """Analyse les données CRM et applique le mapping
        
        Args:
            results: Résultats d'extraction d'iframes
            mapping_data: DataFrame contenant les données de mapping
            selected_columns: Liste des colonnes à inclure dans l'analyse
            id_column: Nom de la colonne contenant les IDs dans le mapping_data
        """
        df = pd.DataFrame(results)
        df['CRM Campaign'] = df['Iframe'].apply(
            lambda x: extract_id_and_code(x)[1])

        if mapping_data is not None and not mapping_data.empty:
            if 'Form ID' not in df.columns:
                return df

            # Créer une copie du DataFrame avec les colonnes sélectionnées
            mapping_subset = mapping_data[[id_column] + [col for col in selected_columns if col != id_column]]
            
            # Renommer la colonne ID pour le mapping
            mapping_subset = mapping_subset.rename(columns={id_column: 'ID'})
            
            # Fusionner avec le DataFrame original
            df = df.merge(
                mapping_subset,
                left_on='Form ID',
                right_on='ID',
                how='left'
            )
            
            # Gérer le cas où CRM_CAMPAIGN est dans les colonnes sélectionnées
            mask = df['CRM Campaign'].isna()
            if 'CRM_CAMPAIGN' in df.columns:
                df.loc[mask, 'CRM Campaign'] = df.loc[mask, 'CRM_CAMPAIGN']
            
            # Supprimer la colonne ID utilisée pour le mapping
            df = df.drop(['ID'], axis=1, errors='ignore')
            
        if self.template_mapping:
            df['Template'] = df['Form ID'].apply(self.get_template_name)

        return df