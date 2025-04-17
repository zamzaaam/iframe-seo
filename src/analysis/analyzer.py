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
        """Applique le mapping basé sur les priorités: 
        1. Valeur présente dans extract
        2. URL + Iframe
        3. Iframe seul
        4. URL + ID (en excluant les IDs des form templates)
        5. ID seul (en excluant les IDs des form templates)
        """
        
        # Préparation du mapping
        mapping_df = mapping_data.copy()
        url_col = mapping_config['url_column']
        iframe_col = mapping_config.get('iframe_column', None)
        id_col = mapping_config.get('id_column', None)
        
        # S'assurer que toutes les colonnes nécessaires existent
        if 'Cluster' not in df.columns:
            df['Cluster'] = None
        
        # DÉTECTION AUTOMATIQUE des colonnes importantes
        crm_column = None
        cluster_column = None
        
        for col in mapping_df.columns:
            if 'crm' in col.lower() and ('code' in col.lower() or 'campaign' in col.lower()):
                crm_column = col
            elif 'cluster' in col.lower():
                cluster_column = col
        
        # Dictionnaires de mapping pour différentes stratégies
        combined_mapping = {}  # URL + Iframe
        iframe_mapping = {}    # Iframe seul
        url_id_mapping = {}    # URL + ID
        id_mapping = {}        # ID seul
        
        # Normalisation pour le matching
        df['normalized_url'] = df['URL source'].str.lower().str.rstrip('/')
        df['normalized_iframe'] = df['Iframe'].str.lower()
        
        # Identifier les template IDs pour les exclure du mapping URL+ID et ID seul
        template_ids = []
        if self.template_mapping:
            template_ids = list(self.template_mapping.keys())
        
        # Préparer les mappings selon les priorités
        
        # 1. Mapping URL+Iframe
        if iframe_col and iframe_col in mapping_df.columns and url_col in mapping_df.columns:
            mapping_df['normalized_url'] = mapping_df[url_col].str.lower().str.rstrip('/')
            mapping_df['normalized_iframe'] = mapping_df[iframe_col].str.lower()
            mapping_df['url_iframe_key'] = mapping_df['normalized_url'] + "||" + mapping_df['normalized_iframe']
            
            df['url_iframe_key'] = df['normalized_url'] + "||" + df['normalized_iframe']
            
            for col in mapping_df.columns:
                if col not in ['url_iframe_key', 'normalized_url', 'normalized_iframe']:
                    combined_mapping[col] = dict(zip(mapping_df['url_iframe_key'], mapping_df[col]))
        
        # 2. Mapping Iframe uniquement
        if iframe_col and iframe_col in mapping_df.columns:
            for col in mapping_df.columns:
                if col not in ['normalized_url', 'normalized_iframe', 'url_iframe_key']:
                    iframe_mapping[col] = dict(zip(mapping_df[iframe_col].str.lower(), mapping_df[col]))
        
        # 3. Mapping URL+ID (en excluant les IDs des form templates)
        if url_col in mapping_df.columns and id_col in mapping_df.columns:
            # Créer une clé combinée URL+ID pour les lignes dont l'ID n'est pas un template ID
            mapping_df['url_id_filtered'] = mapping_df.apply(
                lambda row: mapping_df.loc[row.name, 'normalized_url'] + "||" + str(row[id_col]) 
                            if str(row[id_col]) not in template_ids else None, 
                axis=1
            )
            
            # Créer la même clé dans le DataFrame d'extraction
            df['url_id_filtered'] = df.apply(
                lambda row: row['normalized_url'] + "||" + str(row['Form ID']) 
                            if str(row['Form ID']) not in template_ids else None, 
                axis=1
            )
            
            # Créer le dictionnaire de mapping URL+ID filtré
            for col in mapping_df.columns:
                if col not in ['normalized_url', 'normalized_iframe', 'url_iframe_key', 'url_id_filtered']:
                    # Créer un dictionnaire uniquement avec les lignes non-None
                    valid_keys = mapping_df[mapping_df['url_id_filtered'].notna()]['url_id_filtered']
                    valid_values = mapping_df[mapping_df['url_id_filtered'].notna()][col]
                    if not valid_keys.empty:
                        url_id_mapping[col] = dict(zip(valid_keys, valid_values))
        
        # 4. Mapping ID seul (en excluant les IDs des form templates)
        if id_col in mapping_df.columns:
            # Filtrer pour exclure les IDs des templates
            filtered_mapping_df = mapping_df[~mapping_df[id_col].astype(str).isin(template_ids)]
            
            for col in mapping_df.columns:
                if col not in ['normalized_url', 'normalized_iframe', 'url_iframe_key', 'url_id_filtered']:
                    id_mapping[col] = dict(zip(filtered_mapping_df[id_col].astype(str), filtered_mapping_df[col]))
        
        # Appliquer le mapping selon les priorités
        for idx, row in df.iterrows():
            # Pour CRM Campaign, respecter la priorité:
            # 1. Si déjà présent dans l'extraction, garder cette valeur
            # 2. Sinon, essayer le mapping URL+Iframe
            # 3. Sinon, essayer le mapping Iframe seul
            # 4. Sinon, essayer le mapping URL+ID (excluant les IDs des templates)
            # 5. Sinon, essayer le mapping ID seul (excluant les IDs des templates)
            
            if crm_column and (pd.isna(row['CRM Campaign']) or row['CRM Campaign'] == "None" or row['CRM Campaign'] == ""):
                # Valeur CRM manquante, on peut appliquer le mapping
                
                # D'abord essayer par URL+Iframe
                if 'url_iframe_key' in df.columns and row['url_iframe_key'] in combined_mapping.get(crm_column, {}):
                    df.loc[idx, 'CRM Campaign'] = combined_mapping[crm_column][row['url_iframe_key']]
                # Ensuite par Iframe seul
                elif row['normalized_iframe'] in iframe_mapping.get(crm_column, {}):
                    df.loc[idx, 'CRM Campaign'] = iframe_mapping[crm_column][row['normalized_iframe']]
                # Puis par URL+ID (si l'ID n'est pas un template ID)
                elif ('url_id_filtered' in df.columns and 
                    pd.notna(row['url_id_filtered']) and 
                    row['url_id_filtered'] in url_id_mapping.get(crm_column, {})):
                    df.loc[idx, 'CRM Campaign'] = url_id_mapping[crm_column][row['url_id_filtered']]
                # Enfin par ID seul (si l'ID n'est pas un template ID)
                elif str(row['Form ID']) not in template_ids and str(row['Form ID']) in id_mapping.get(crm_column, {}):
                    df.loc[idx, 'CRM Campaign'] = id_mapping[crm_column][str(row['Form ID'])]
            
            # Traitement pour Cluster et autres colonnes sélectionnées avec les mêmes priorités
            if cluster_column:
                if pd.isna(row['Cluster']) or row['Cluster'] == "None" or row['Cluster'] == "":
                    # D'abord essayer par URL+Iframe
                    if 'url_iframe_key' in df.columns and row['url_iframe_key'] in combined_mapping.get(cluster_column, {}):
                        df.loc[idx, 'Cluster'] = combined_mapping[cluster_column][row['url_iframe_key']]
                    # Ensuite par Iframe seul
                    elif row['normalized_iframe'] in iframe_mapping.get(cluster_column, {}):
                        df.loc[idx, 'Cluster'] = iframe_mapping[cluster_column][row['normalized_iframe']]
                    # Puis par URL+ID (si l'ID n'est pas un template ID)
                    elif ('url_id_filtered' in df.columns and 
                        pd.notna(row['url_id_filtered']) and 
                        row['url_id_filtered'] in url_id_mapping.get(cluster_column, {})):
                        df.loc[idx, 'Cluster'] = url_id_mapping[cluster_column][row['url_id_filtered']]
                    # Enfin par ID seul (si l'ID n'est pas un template ID)
                    elif str(row['Form ID']) not in template_ids and str(row['Form ID']) in id_mapping.get(cluster_column, {}):
                        df.loc[idx, 'Cluster'] = id_mapping[cluster_column][str(row['Form ID'])]
            
            # Traitement des autres colonnes sélectionnées
            if mapping_config and 'selected_columns' in mapping_config:
                selected_cols = [col for col in mapping_config['selected_columns'] 
                                if col != crm_column and col != cluster_column]
                
                for col in selected_cols:
                    if col not in df.columns:
                        df[col] = None
                        
                    if pd.isna(row[col]) or row[col] == "None" or row[col] == "":
                        # D'abord essayer par URL+Iframe
                        if 'url_iframe_key' in df.columns and row['url_iframe_key'] in combined_mapping.get(col, {}):
                            df.loc[idx, col] = combined_mapping[col][row['url_iframe_key']]
                        # Ensuite par Iframe seul
                        elif row['normalized_iframe'] in iframe_mapping.get(col, {}):
                            df.loc[idx, col] = iframe_mapping[col][row['normalized_iframe']]
                        # Puis par URL+ID (si l'ID n'est pas un template ID)
                        elif ('url_id_filtered' in df.columns and 
                            pd.notna(row['url_id_filtered']) and 
                            row['url_id_filtered'] in url_id_mapping.get(col, {})):
                            df.loc[idx, col] = url_id_mapping[col][row['url_id_filtered']]
                        # Enfin par ID seul (si l'ID n'est pas un template ID)
                        elif str(row['Form ID']) not in template_ids and str(row['Form ID']) in id_mapping.get(col, {}):
                            df.loc[idx, col] = id_mapping[col][str(row['Form ID'])]
        
        # Assurer la cohérence des types de données
        if 'CRM Campaign' in df.columns:
            df['CRM Campaign'] = df['CRM Campaign'].astype(str)
        
        # Nettoyage des colonnes temporaires
        for col in ['normalized_url', 'normalized_iframe', 'url_iframe_key', 'url_id_filtered']:
            if col in df.columns:
                df = df.drop(col, axis=1)
        
        return df


    def _apply_crm_mapping(self, df: pd.DataFrame, crm_data: pd.DataFrame, 
                      crm_mapping_config: Dict) -> pd.DataFrame:
        
        """Applique le mapping basé sur les codes de campagne CRM avec logique 'starts with'"""
        
        import numpy as np
        
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
        
        # CORRECTION DES VALEURS SPÉCIALES DANS LE DATAFRAME D'EXTRACTION
        # Remplacer 'None', 'NaN', etc. par des NaN véritables
        df['CRM Campaign'] = df['CRM Campaign'].replace(['None', 'NONE', 'NaN', 'NAN', 'none', 'nan'], np.nan)
        
        # NORMALISATION DES CODES CRM
        # Créer une colonne normalisée pour les codes CRM, en excluant les NaN
        df['normalized_crm_code'] = df['CRM Campaign'].astype(str)
        mask = ~df['CRM Campaign'].isna() & (df['CRM Campaign'] != 'nan')
        df.loc[mask, 'normalized_crm_code'] = df.loc[mask, 'CRM Campaign'].str.strip().str.upper()
        
        # Normalisation dans le dataframe CRM
        crm_data_copy = crm_data.copy()
        crm_data_copy['normalized_crm_code'] = crm_data_copy[crm_code_col].astype(str).str.strip().str.upper()
        
        # Fonction pour trouver le meilleur match par préfixe
        def find_best_match(code, code_dict):
            if pd.isna(code) or code == 'nan' or code == 'None':
                return None
                
            # 1. Essayer une correspondance exacte d'abord
            if code in code_dict:
                return code_dict[code]
                
            # 2. Essayer une correspondance par préfixe
            for full_code in code_dict.keys():
                # Si le code partiel est un préfixe du code complet
                if full_code.startswith(code):
                    return code_dict[full_code]
                
            # 3. Si le code partiel est plus long, vérifier s'il commence par un code connu
            for full_code in code_dict.keys():
                if code.startswith(full_code):
                    return code_dict[full_code]
                    
            return None
        
        # Appliquer le mapping colonne par colonne avec logique "starts with"
        for col_name in selected_columns:
            if col_name != crm_code_col and col_name in crm_data_copy.columns:
                # Créer un dictionnaire de mapping pour cette colonne
                mapping_dict = dict(zip(crm_data_copy['normalized_crm_code'], crm_data_copy[col_name]))
                
                # Nouvelle colonne avec préfixe CRM_
                new_col_name = f"CRM_{col_name}"
                
                # Initialiser la colonne
                df[new_col_name] = None
                
                # Appliquer le mapping avec logique "starts with"
                for idx, row in df.iterrows():
                    if pd.notna(row['normalized_crm_code']):
                        match_value = find_best_match(row['normalized_crm_code'], mapping_dict)
                        if match_value is not None:
                            df.loc[idx, new_col_name] = match_value
        
        # Nettoyage de la colonne temporaire
        if 'normalized_crm_code' in df.columns:
            df = df.drop('normalized_crm_code', axis=1)
        
        return df