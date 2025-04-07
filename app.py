import streamlit as st
import pandas as pd
import requests
import json
import os
from dotenv import load_dotenv
import re
import time
import pickle
from pathlib import Path

# Carrega variáveis de ambiente
load_dotenv()

# Configura API Open Router
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
SITE_URL = os.getenv('SITE_URL', 'https://localhost:8501')
SITE_NAME = os.getenv('SITE_NAME', 'Calculadora de Pesos')

# Caminho para o arquivo de glossário de densidades
DENSIDADES_PATH = Path("densidades.pkl")


def carregar_glossario_densidades():
    """
    Carrega o glossário de densidades do arquivo, ou cria um novo se não existir.
    """
    if DENSIDADES_PATH.exists():
        try:
            with open(DENSIDADES_PATH, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            st.error(f"Erro ao carregar glossário de densidades: {e}")
            return {}
    else:
        # Cria um glossário inicial com alguns valores comuns
        glossario_inicial = {
            "cimento": {"densidade": 1400, "unidade": "kg/m³", "descricao": "Cimento Portland comum"},
            "areia": {"densidade": 1600, "unidade": "kg/m³", "descricao": "Areia média seca"},
            "brita": {"densidade": 1500, "unidade": "kg/m³", "descricao": "Brita comum"},
            "concreto": {"densidade": 2400, "unidade": "kg/m³", "descricao": "Concreto estrutural"},
            "aço": {"densidade": 7850, "unidade": "kg/m³", "descricao": "Aço estrutural"},
            "madeira pinho": {"densidade": 600, "unidade": "kg/m³", "descricao": "Madeira de pinho"},
            "tijolo": {"densidade": 1800, "unidade": "kg/m³", "descricao": "Tijolo cerâmico"},
            "gesso": {"densidade": 1000, "unidade": "kg/m³", "descricao": "Gesso em pó"},
            "tinta": {"densidade": 1300, "unidade": "kg/m³", "descricao": "Tinta látex"},
            "vidro": {"densidade": 2500, "unidade": "kg/m³", "descricao": "Vidro comum"},
            "pvc": {"densidade": 1400, "unidade": "kg/m³", "descricao": "PVC"},
            "alumínio": {"densidade": 2700, "unidade": "kg/m³", "descricao": "Alumínio"},
            "argamassa": {"densidade": 1900, "unidade": "kg/m³", "descricao": "Argamassa comum"},
            "adubo orgânico": {"densidade": 700, "unidade": "kg/m³", "descricao": "Adubo orgânico curtido"}
        }
        salvar_glossario_densidades(glossario_inicial)
        return glossario_inicial

def salvar_glossario_densidades(glossario):
    """
    Salva o glossário de densidades em um arquivo.
    """
    try:
        with open(DENSIDADES_PATH, 'wb') as f:
            pickle.dump(glossario, f)
    except Exception as e:
        st.error(f"Erro ao salvar glossário de densidades: {e}")

def atualizar_glossario_densidades(material, densidade, unidade="kg/m³", descricao=None):
    """
    Atualiza o glossário de densidades com um novo material ou atualiza um existente.
    """
    glossario = carregar_glossario_densidades()
    material = material.lower().strip()
    
    if descricao is None:
        descricao = f"Material: {material}"
    
    glossario[material] = {
        "densidade": densidade,
        "unidade": unidade,
        "descricao": descricao
    }
    
    salvar_glossario_densidades(glossario)
    return glossario

def limpar_numero(texto):
    """
    Limpa e converte texto numérico para float, tratando vários formatos.
    Garante que o separador decimal seja sempre ponto.
    """
    if isinstance(texto, (int, float)):
        return float(texto)
        
    if not isinstance(texto, str):
        return None
        
    # Remove 'kg' e qualquer outro texto
    texto = re.sub(r'[^\d.,\-]', '', texto)
    
    # Trata diferentes formatos de números
    try:
        # Se tem vírgula e ponto, assume que vírgula é separador de milhares
        if ',' in texto and '.' in texto:
            texto = texto.replace(',', '')
        # Se tem só vírgula, assume que é separador decimal
        elif ',' in texto:
            texto = texto.replace(',', '.')
            
        return float(texto)
    except:
        return None

def verificar_unidade_basica(quantidade, unidade):
    """
    Verifica se a unidade é kg ou tonelada e faz a conversão direta.
    Retorna uma tupla (peso_em_kg, memorial) ou (None, None) se não for unidade básica.
    """
    if not isinstance(unidade, str):
        return None, None
        
    unidade = unidade.lower().strip()
    
    # Verifica se já está em kg
    if unidade in ['kg', 'kgs', 'quilos', 'quilograma', 'quilogramas']:
        return quantidade, "Valor já está em kg, não necessita conversão."
        
    # Verifica se está em toneladas
    if unidade in ['t', 'ton', 'tons', 'tonelada', 'toneladas']:
        peso = quantidade * 1000
        return peso, f"Conversão direta: {quantidade} toneladas = {peso:.2f} kg"
        
    return None, None

def calcular_peso_com_llm(descricao, quantidade, unidade):
    """
    Usa LLM para calcular peso baseado na descrição, quantidade e unidade do insumo.
    Primeiro verifica se é possível fazer conversão direta de unidades básicas.
    """
    try:
        # Primeiro tenta converter unidades básicas
        peso, memorial = verificar_unidade_basica(quantidade, unidade)
        if peso is not None:
            return peso, memorial, "", ""

        # Carrega o glossário de densidades
        glossario = carregar_glossario_densidades()
        
        # Prepara uma lista de materiais conhecidos para o prompt
        materiais_conhecidos = ""
        for material, info in glossario.items():
            materiais_conhecidos += f"- {material}: {info['densidade']} {info['unidade']} ({info['descricao']})\n"
        
        # Se não for unidade básica, usa a API Open Router
        prompt = f"""
        Calcule o peso em kg para o seguinte insumo:
        - Descrição: {descricao}
        - Quantidade: {quantidade}
        - Unidade de Medida: {unidade}

        Pense de maneira passo a passo.
        
        IMPORTANTE: Utilize SEMPRE as densidades conhecidas abaixo quando aplicável. Caso o material não esteja na lista, use uma densidade padrão baseada em materiais similares e INDIQUE CLARAMENTE que está usando uma estimativa.
        
        DENSIDADES CONHECIDAS:
        {materiais_conhecidos}
        
        Forneça sua resposta EXATAMENTE neste formato:
        Peso: [número em kg, use ponto como separador decimal]
        Memorial: [sua explicação detalhada incluindo a densidade utilizada e cálculos]
        Forma de comercialização: [forneça como esse material é usualmente comercializado]
        Nova densidade: [se você usou uma densidade que não está na lista acima, forneça o valor aqui no formato número kg/m³, caso contrário deixe em branco]

        Exemplo de resposta correta:
        Peso: 5 kg
        Memorial: Para madeira compensada, considerando densidade média de 0.5 kg/dm³ e uma quantidade de 10 dm³ e a unidade de dm³, o peso total é 0.5 (kg/dm3) * 10 (dm³) = 5 kg. O resultado SEMPRE será em kg.
        Forma de comercialização: Usualmente comercializado em placas 1m x 1m.
        Nova densidade: 
        
        Outro exemplo com nova densidade:
        Peso: 850 kg
        Memorial: Para o saco de cimento, considerando densidade média de 42,5 kg/saco e uma quantidade de 20 sacos e a unidade em saco, o peso total é 42.5 (kg/saco) * 20 (saco) = 850 kg. O resultado SEMPRE será em kg.
        Forma de comercialização: Usualmente comercializado em sacos de 42,5 kg.
        Nova densidade: 1400 kg/m³
        """

        # Chama API Open Router
        try:
            resposta = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "HTTP-Referer": SITE_URL,
                    "X-Title": SITE_NAME,
                    "Content-Type": "application/json",
                },
                json={
                    "model": "google/gemini-flash-1.5-8b",
                    "messages": [
                        {
                            "role": "system",
                            "content": "Você é um assistente técnico especializado em calcular pesos de materiais de construção. Use SEMPRE ponto como separador decimal, nunca vírgula."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                }
            )
            
            # Verifica se a requisição foi bem sucedida
            resposta.raise_for_status()
            
            # Parse da resposta JSON
            resposta_json = resposta.json()
            
            if "error" in resposta_json:
                raise Exception(f"Erro da API: {resposta_json['error']}")
                
            # Extrai a resposta do modelo
            if "choices" not in resposta_json:
                raise Exception(f"Formato de resposta inesperado: {resposta_json}")
                
            resposta_completa = resposta_json["choices"][0]["message"]["content"].strip()
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro na chamada da API: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Erro ao decodificar resposta JSON: {str(e)}")
        except Exception as e:
            raise Exception(f"Erro inesperado: {str(e)}")

        # Divide a resposta em peso, memorial, forma de comercialização e nova densidade
        linhas = resposta_completa.split('\n')
        texto_peso = linhas[0].split(':')[1].strip() if len(linhas) > 0 and ':' in linhas[0] else ""
        
        # Limpa e converte o peso
        peso = limpar_numero(texto_peso)
        if peso is None:
            raise ValueError(f"Não foi possível converter o peso: {texto_peso}")
        
        # Inicializa as variáveis
        memorial = ""
        forma_comercializacao = ""
        nova_densidade_texto = ""
        nova_densidade_valor = ""
        
        # Extrai cada parte da resposta
        for linha in linhas[1:]:
            if linha.startswith("Memorial:") and ':' in linha:
                memorial = linha.split(':', 1)[1].strip()
            elif linha.startswith("Forma de comercialização:") and ':' in linha:
                forma_comercializacao = linha.split(':', 1)[1].strip()
            elif linha.startswith("Nova densidade:") and ':' in linha:
                nova_densidade_texto = linha.split(':', 1)[1].strip()
                if nova_densidade_texto and nova_densidade_texto != "":
                    try:
                        # Extrai o valor numérico da densidade
                        match = re.search(r'(\d+([.,]\d+)?)', nova_densidade_texto)
                        if match:
                            nova_densidade = float(match.group(1).replace(',', '.'))
                            nova_densidade_valor = f"{nova_densidade} kg/m³"
                            
                            # Extrai o nome do material da descrição
                            palavras_chave = descricao.lower().split()
                            material_nome = palavras_chave[0] if palavras_chave else "material"
                            for palavra in palavras_chave:
                                if palavra in ["de", "do", "da", "para", "com", "em", "no", "na", "e", "o", "a"]:
                                    continue
                                material_nome = palavra
                                break
                            
                            # Atualiza o glossário com a nova densidade
                            atualizar_glossario_densidades(
                                material_nome, 
                                nova_densidade, 
                                "kg/m³", 
                                descricao
                            )
                            st.success(f"Nova densidade adicionada ao glossário: {material_nome} = {nova_densidade} kg/m³")
                    except Exception as e:
                        st.warning(f"Não foi possível processar a nova densidade: {e}")

        return peso, memorial, forma_comercializacao, nova_densidade_valor

    except Exception as e:
        st.error(f"Erro ao calcular peso: {e}")
        return None, None, None, None

def principal():
    st.title('Calculadora de Pesos de Insumos')
    
    # Carrega o glossário de densidades
    glossario = carregar_glossario_densidades()
    
    # Adiciona uma seção para gerenciar o glossário de densidades
    with st.expander("Gerenciar Glossário de Densidades"):
        st.write("### Glossário de Densidades Conhecidas")
        
        # Exibe o glossário atual em uma tabela
        glossario_df = pd.DataFrame([
            {
                "Material": material,
                "Densidade": info["densidade"],
                "Unidade": info["unidade"],
                "Descrição": info["descricao"]
            }
            for material, info in glossario.items()
        ])
        
        if not glossario_df.empty:
            st.dataframe(glossario_df)
        else:
            st.info("Nenhuma densidade cadastrada ainda.")
        
        # Formulário para adicionar nova densidade
        st.write("### Adicionar Nova Densidade")
        with st.form("nova_densidade_form"):
            col1, col2 = st.columns(2)
            with col1:
                novo_material = st.text_input("Material")
                nova_densidade = st.number_input("Densidade", min_value=0.0, format="%f")
            with col2:
                nova_unidade = st.selectbox("Unidade", options=["kg/m³", "kg/L", "kg/dm³", "g/cm³"])
                nova_descricao = st.text_input("Descrição")
            
            submitted = st.form_submit_button("Adicionar ao Glossário")
            if submitted and novo_material and nova_densidade > 0:
                atualizar_glossario_densidades(novo_material, nova_densidade, nova_unidade, nova_descricao)
                st.success(f"Densidade para {novo_material} adicionada com sucesso!")
                st.experimental_rerun()
    
    # Upload do arquivo
    arquivo_carregado = st.file_uploader("Escolha uma planilha de insumos", type=['xlsx', 'xls'])
    
    if arquivo_carregado is not None:
        try:
            # Lê o arquivo Excel começando da linha 6 (índice 5)
            df = pd.read_excel(
                arquivo_carregado,
                skiprows=5,  # Pula as primeiras 5 linhas
                usecols=[2, 4, 5],  # Usa colunas D (índice 3), F (5) e G (6)
                names=['Descrição', 'Unidade', 'Quantidade'],  # Renomeia colunas
                decimal=','  # Especifica que vírgula é o separador decimal no Excel
            )
            
            # Remove linhas completamente vazias
            df = df.dropna(how='all')
            
            # Converte a coluna Quantidade para número, tratando diferentes formatos
            df['Quantidade'] = df['Quantidade'].apply(limpar_numero)
            
            # Exibe dataframe original
            st.subheader('Planilha Original')
            
            # Configura o formato de exibição para usar ponto como separador decimal
            pd.options.display.float_format = '{:.2f}'.format
            st.dataframe(df)
            
            # Prepara para cálculo dos pesos
            st.subheader('Calculando Pesos')
            barra_progresso = st.progress(0)
            
            # Novas colunas para peso, memorial e outras informações
            df['Peso (kg)'] = None
            df['Memorial'] = None
            df['Forma de Comercialização'] = None
            df['Nova Densidade'] = None
            
            # Calcula pesos
            for indice, linha in df.iterrows():
                descricao = linha['Descrição']
                quantidade = linha['Quantidade']
                unidade = linha['Unidade']
                
                if pd.notna(descricao) and pd.notna(quantidade) and pd.notna(unidade):
                    # Calcula peso
                    peso, memorial, forma_comercializacao, nova_densidade = calcular_peso_com_llm(descricao, quantidade, unidade)
                    
                    # Atualiza dataframe
                    df.at[indice, 'Peso (kg)'] = peso
                    df.at[indice, 'Memorial'] = memorial
                    df.at[indice, 'Forma de Comercialização'] = forma_comercializacao
                    df.at[indice, 'Nova Densidade'] = nova_densidade
                
                # Atualiza progresso
                barra_progresso.progress((indice + 1) / len(df))
            
            # Exibe dataframe atualizado
            st.subheader('Planilha com Pesos Calculados')
            st.dataframe(df)
            
            # Opção de download
            # Configura o formato CSV para usar ponto como separador decimal
            csv = df.to_csv(index=False, decimal='.')
            st.download_button(
                label="Baixar Planilha Atualizada",
                data=csv,
                file_name='insumos_com_pesos.csv',
                mime='text/csv'
            )
            
            # Recarrega o glossário para mostrar as novas densidades adicionadas
            glossario_atualizado = carregar_glossario_densidades()
            
            # Atualiza a exibição do glossário na interface
            with st.expander("Glossário de Densidades Atualizado"):
                st.write("### Glossário de Densidades (Incluindo Novas Adições)")
                
                # Exibe o glossário atualizado em uma tabela
                glossario_df = pd.DataFrame([
                    {
                        "Material": material,
                        "Densidade": info["densidade"],
                        "Unidade": info["unidade"],
                        "Descrição": info["descricao"]
                    }
                    for material, info in glossario_atualizado.items()
                ])
                
                if not glossario_df.empty:
                    st.dataframe(glossario_df)
                else:
                    st.info("Nenhuma densidade cadastrada ainda.")
            
            # Memorial detalhado
            st.subheader('Memoriais de Cálculo')
            
            # Cria tabs para organizar os memoriais
            num_itens = len(df[df['Memorial'].notna()])
            if num_itens > 0:
                # Cria abas para cada item ou agrupa em categorias se houver muitos
                if num_itens <= 10:
                    # Cria uma aba para cada item
                    tabs = st.tabs([f"Item {i+1}" for i, _ in enumerate(df[df['Memorial'].notna()].iterrows())])
                    
                    # Preenche cada aba com as informações do memorial
                    tab_index = 0
                    for indice, linha in df.iterrows():
                        if pd.notna(linha.get('Memorial')):
                            with tabs[tab_index]:
                                col1, col2 = st.columns([2, 1])
                                with col1:
                                    st.markdown(f"### {linha['Descrição']}")
                                    # Exibe as informações separadas em seções distintas
                                    st.markdown("### Memorial de Cálculo")
                                    st.markdown(linha.get('Memorial', 'Não calculado'))
                                    
                                    st.markdown("### Forma de Comercialização")
                                    st.markdown(linha.get('Forma de Comercialização', 'Não informado'))
                                    
                                    if pd.notna(linha.get('Nova Densidade')) and linha.get('Nova Densidade') != "":
                                        st.markdown("### Nova Densidade")
                                        st.markdown(linha.get('Nova Densidade', ''))
                                with col2:
                                    # Cria um card com as informações principais
                                    st.markdown("### Resumo")
                                    st.markdown(f"**Quantidade:** {linha['Quantidade']} {linha['Unidade']}")
                                    peso = linha.get('Peso (kg)')
                                    if pd.notna(peso):
                                        st.markdown(f"**Peso calculado:** {peso:.2f} kg")
                                    else:
                                        st.markdown("**Peso calculado:** N/A")
                            tab_index += 1
                else:
                    # Cria um expander para cada item
                    for indice, linha in df.iterrows():
                        if pd.notna(linha.get('Memorial')):
                            with st.expander(f"Item {indice+1}: {linha['Descrição']}"):
                                col1, col2 = st.columns([2, 1])
                                with col1:
                                    # Exibe as informações separadas em seções distintas
                                    st.markdown("### Memorial de Cálculo")
                                    st.markdown(linha.get('Memorial', 'Não calculado'))
                                    
                                    st.markdown("### Forma de Comercialização")
                                    st.markdown(linha.get('Forma de Comercialização', 'Não informado'))
                                    
                                    if pd.notna(linha.get('Nova Densidade')) and linha.get('Nova Densidade') != "":
                                        st.markdown("### Nova Densidade")
                                        st.markdown(linha.get('Nova Densidade', ''))
                                with col2:
                                    # Cria um card com as informações principais
                                    st.markdown("### Resumo")
                                    st.markdown(f"**Quantidade:** {linha['Quantidade']} {linha['Unidade']}")
                                    peso = linha.get('Peso (kg)')
                                    if pd.notna(peso):
                                        st.markdown(f"**Peso calculado:** {peso:.2f} kg")
                                    else:
                                        st.markdown("**Peso calculado:** N/A")
            else:
                st.info("Nenhum memorial de cálculo disponível.")
        
        except Exception as e:
            st.error(f"Erro ao processar planilha: {e}")

if __name__ == "__main__":
    principal()
