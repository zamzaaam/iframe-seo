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

    def analyze_crm_data(self, 
                        results: List[Dict], 
                        url_mapping_data: Optional[pd.DataFrame] = None, 
                        url_mapping_config: Optional[Dict] = None,
                        crm_data: Optional[pd.DataFrame] = None,
                        crm_mapping_config: Optional[Dict] = None) -> pd.DataFrame:
        """
        Analyse les données en intégrant:
        1. Les résultats d'extraction
        2. Les données de mapping URL-Form (optionnel)
        3. Les données CRM par code de campagne (optionnel)
        """
        # Filtrer les résultats vides
        results = [r for r in results if r.get('Iframe') and r.get('URL source') and r.get('Form ID')]
        
        if not results:
            return pd.DataFrame(columns=['URL source', 'Iframe', 'Form ID', 'CRM Campaign', 'Template'])
        
        # Créer le DataFrame de base
        df = pd.DataFrame(results)
        
        # Extraction des codes CRM de l'URL
        df['CRM Campaign'] = df['Iframe'].apply(
            lambda x: extract_id_and_code(x)[1])
        
        # Ajout des noms de template
        if 'Form ID' in df.columns and self.template_mapping:
            df['Template'] = df['Form ID'].apply(self.get_template_name)

        # === ÉTAPE 1: Appliquer le mapping URL si disponible ===
        if url_mapping_data is not None and url_mapping_config is not None:
            df = self._apply_url_mapping(df, url_mapping_data, url_mapping_config)
        
        # === ÉTAPE 2: Appliquer le mapping CRM si disponible ===
        if crm_data is not None and crm_mapping_config is not None:
            df = self._apply_crm_mapping(df, crm_data, crm_mapping_config)
        
        return df

    def _apply_url_mapping(self, df: pd.DataFrame, mapping_data: pd.DataFrame, 
                           mapping_config: Dict) -> pd.DataFrame:
        """Applique le mapping basé sur les URLs et Form IDs"""
        
        # Préparation du mapping
        mapping_df = mapping_data.copy()
        url_col = mapping_config['url_column']
        id_col = mapping_config['id_column']
        
        # DÉTECTION AUTOMATIQUE des colonnes importantes
        crm_column = None
        cluster_column = None
        
        for col in mapping_df.columns:
            if 'crm' in col.lower() and ('code' in col.lower() or 'campaign' in col.lower()):
                crm_column = col
            elif 'cluster' in col.lower():
                cluster_column = col
        
        # Créer des dictionnaires de mapping basés sur l'URL
        url_mapping = {}
        if url_col in mapping_df.columns:
            for col in mapping_df.columns:
                if col != url_col and col != id_col:
                    url_mapping[col] = dict(zip(mapping_df[url_col], mapping_df[col]))
        
        # Créer des dictionnaires de mapping basés sur l'ID (fallback)
        id_mapping = {}
        if id_col in mapping_df.columns:
            for col in mapping_df.columns:
                if col != url_col and col != id_col:
                    id_mapping[col] = dict(zip(mapping_df[id_col], mapping_df[col]))
        
        # Appliquer le mapping aux résultats
        for idx, row in df.iterrows():
            url = row['URL source']
            form_id = row['Form ID']
            
            # Traitement spécial pour CRM Campaign
            if crm_column and (pd.isna(row['CRM Campaign']) or row['CRM Campaign'] == "None" or row['CRM Campaign'] == ""):
                # D'abord essayer par URL
                if url in url_mapping.get(crm_column, {}):
                    df.at[idx, 'CRM Campaign'] = url_mapping[crm_column][url]
                # Sinon par ID
                elif form_id in id_mapping.get(crm_column, {}):
                    df.at[idx, 'CRM Campaign'] = id_mapping[crm_column][form_id]
            
            # Traitement pour Cluster - UNIQUEMENT par URL
            if cluster_column:
                if url in url_mapping.get(cluster_column, {}):
                    df.at[idx, 'Cluster'] = url_mapping[cluster_column][url]
        
        # Si d'autres colonnes sont explicitement sélectionnées, les ajouter aussi
        if mapping_config and 'selected_columns' in mapping_config:
            selected_cols = [col for col in mapping_config['selected_columns'] 
                            if col != crm_column and col != cluster_column]
            
            for col in selected_cols:
                for idx, row in df.iterrows():
                    url = row['URL source']
                    form_id = row['Form ID']
                    
                    # D'abord essayer par URL puis par ID
                    if url in url_mapping.get(col, {}):
                        df.at[idx, col] = url_mapping[col][url]
                    elif form_id in id_mapping.get(col, {}):
                        df.at[idx, col] = id_mapping[col][form_id]
        
        return df

    def _apply_crm_mapping(self, df: pd.DataFrame, crm_data: pd.DataFrame, 
                          crm_mapping_config: Dict) -> pd.DataFrame:
        """Applique le mapping basé sur les codes de campagne CRM"""
        
        if 'CRM Campaign' not in df.columns:
            return df
            
        # Vérifier qu'il y a des codes CRM dans le DataFrame
        if df['CRM Campaign'].isna().all():
            return df
            
        # Récupérer la colonne contenant les codes CRM dans le fichier de mapping
        crm_code_col = crm_mapping_config.get('crm_code_column')
        if not crm_code_col or crm_code_col not in crm_data.columns:
            return df
            
        # Colonnes à inclure depuis les données CRM
        selected_columns = crm_mapping_config.get('selected_columns', [])
        if not selected_columns:
            return df
            
        # Créer un dictionnaire de mapping pour chaque colonne sélectionnée
        crm_mappings = {}
        for col in selected_columns:
            if col != crm_code_col and col in crm_data.columns:
                crm_mappings[col] = dict(zip(crm_data[crm_code_col], crm_data[col]))
        
        # Appliquer le mapping aux résultats
        for col_name, mapping_dict in crm_mappings.items():
            # Créer une nouvelle colonne avec préfixe CRM_
            new_col_name = f"CRM_{col_name}"
            
            # Appliquer le mapping
            df[new_col_name] = df['CRM Campaign'].map(mapping_dict)
        
        return df