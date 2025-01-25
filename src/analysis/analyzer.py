import pandas as pd
from typing import List, Dict
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

    def get_template_name(self, form_id: str) -> str:
        """Récupère le nom du template pour un ID donné"""
        if not form_id or not self.template_mapping:
            return None
        return self.template_mapping.get(form_id)

    def analyze_crm_data(self, results: List[Dict], mapping_data: pd.DataFrame = None) -> pd.DataFrame:
        """Analyse les données CRM et applique le mapping"""
        df = pd.DataFrame(results)
        df['CRM Campaign'] = df['Iframe'].apply(
            lambda x: extract_id_and_code(x)[1])

        if mapping_data is not None:
            df = df.merge(
                mapping_data,
                left_on='Form ID',
                right_on='ID',
                how='left'
            )
            mask = df['CRM Campaign'].isna()
            if 'CRM_CAMPAIGN' in df.columns:
                df.loc[mask, 'CRM Campaign'] = df.loc[mask, 'CRM_CAMPAIGN']
            df = df.drop(['ID'], axis=1, errors='ignore')

        if self.template_mapping:
            df['Template'] = df['Form ID'].apply(self.get_template_name)

        return df
