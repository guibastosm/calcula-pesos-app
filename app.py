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
        
    # Remove unidades e texto, mantém números, pontos, vírgulas e sinais
    texto = re.sub(r'[^\d.,\-\s]', '', texto)
    texto = texto.strip()
    
    # Trata diferentes formatos de números
    try:
        # Formato brasileiro: 1.000,50 ou 3.324,0979121
        if re.match(r'^\d{1,3}(\.\d{3})*,\d+$', texto):
            texto = texto.replace('.', '').replace(',', '.')
        # Formato americano: 1,000.50
        elif re.match(r'^\d{1,3}(,\d{3})*\.\d+$', texto):
            texto = texto.replace(',', '')
        # Se tem só vírgula, assume que é separador decimal
        elif ',' in texto and '.' not in texto:
            texto = texto.replace(',', '.')
        # Se tem ponto e vírgula, mas não no formato padrão, tenta limpar
        elif ',' in texto and '.' in texto:
            # Remove pontos que são separadores de milhares
            if texto.count('.') > 1 or texto.rfind(',') > texto.rfind('.'):
                texto = texto.replace('.', '').replace(',', '.')
            else:
                texto = texto.replace(',', '')
            
        return float(texto)
    except ValueError:
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

def extrair_resposta_ia(resposta_completa):
    """
    Extrai informações da resposta da IA de forma mais robusta usando regex.
    """
    resultado = {
        'peso': None,
        'memorial': '',
        'forma_comercializacao': '',
        'nova_densidade': ''
    }
    
    # Usar regex para extrair cada campo de forma mais robusta
    patterns = {
        'peso': r'Peso:\s*([0-9.,]+)',
        'memorial': r'Memorial:\s*(.+?)(?=\n(?:Forma|Nova densidade|$))',
        'forma_comercializacao': r'Forma de comercialização:\s*(.+?)(?=\n(?:Nova densidade|$))',
        'nova_densidade': r'Nova densidade:\s*(.+?)(?=\n|$)'
    }
    
    for campo, pattern in patterns.items():
        match = re.search(pattern, resposta_completa, re.IGNORECASE | re.DOTALL)
        if match:
            valor = match.group(1).strip()
            if campo == 'peso':
                resultado[campo] = limpar_numero(valor)
            else:
                resultado[campo] = valor
    
    return resultado

def eh_unidade_tempo_ou_energia(unidade):
    """
    Verifica se a unidade está relacionada a tempo, energia ou serviços e deve ser ignorada.
    """
    if not isinstance(unidade, str):
        return False
    
    unidade = unidade.lower().strip()
    
    # Lista de unidades de tempo para ignorar
    unidades_tempo = [
        # Horas
        'h', 'hr', 'hrs', 'hora', 'horas',
        # Dias
        'd', 'dia', 'dias', 'day', 'days',
        # Semanas
        'sem', 'semana', 'semanas', 'week', 'weeks',
        # Meses
        'mes', 'mês', 'meses', 'month', 'months',
        # Anos
        'ano', 'anos', 'year', 'years',
        # Minutos
        'min', 'minuto', 'minutos', 'minute', 'minutes',
        # Segundos
        's', 'seg', 'segundo', 'segundos', 'second', 'seconds',
        # Outras unidades temporais
        'trimestre', 'bimestre', 'quinzena', 'década'
    ]
    
    # Lista de unidades de energia/potência para ignorar
    unidades_energia = [
        # Energia elétrica
        'kwh', 'kw/h', 'kw-h', 'mwh', 'wh',
        # Potência
        'hp', 'cv', 'kw', 'w', 'watt', 'watts',
        # Outras unidades elétricas
        'va', 'kva', 'var', 'kvar', 'volt', 'volts', 'amp', 'amps'
    ]
    
    return unidade in unidades_tempo or unidade in unidades_energia

def validar_configuracao_api():
    """
    Valida se a configuração da API OpenRouter está correta.
    """
    if not OPENROUTER_API_KEY:
        st.error("❌ OPENROUTER_API_KEY não configurada!")
        st.info("💡 Configure a chave da API no arquivo .env")
        return False
    
    if OPENROUTER_API_KEY.startswith('sk-or-'):
        return True
    else:
        st.warning("⚠️ Formato da API Key pode estar incorreto. Chaves OpenRouter geralmente começam com 'sk-or-'")
        return True  # Permite continuar mesmo com formato diferente

def calcular_peso_com_llm(descricao, quantidade, unidade):
    """
    Usa LLM para calcular peso baseado na descrição, quantidade e unidade do insumo.
    Primeiro verifica se é possível fazer conversão direta de unidades básicas.
    """
    try:
        # Limpa e converte quantidade para float, depois arredonda para 2 casas decimais
        quantidade_limpa = limpar_numero(quantidade)
        if quantidade_limpa is None:
            raise ValueError(f"Não foi possível converter a quantidade: {quantidade}")
        quantidade_arredondada = round(quantidade_limpa, 2)
        
        # Primeiro tenta converter unidades básicas
        peso, memorial = verificar_unidade_basica(quantidade_arredondada, unidade)
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
        - Quantidade: {quantidade_arredondada}
        - Unidade de Medida: {unidade}

        Pense de maneira passo a passo e seja PRECISO nos cálculos matemáticos.
        
        IMPORTANTE: 
        1. Utilize SEMPRE as densidades conhecidas abaixo quando aplicável
        2. Para unidade "un" (unidade): ANALISE a descrição para estimar peso individual realista
        3. Faça cálculos matemáticos EXATOS: peso_individual × quantidade = peso_total
        4. NUNCA converta o resultado para toneladas - mantenha SEMPRE em kg
        5. Para grandes quantidades (ex: 1500 × 484.53 = 726795 kg), NÃO arredonde para milhares
        6. Para TUBOS: use a fórmula Volume = 2×π×(Diâmetro/2)×Espessura×Altura para calcular o volume de material
        7. Caso o material não esteja na lista, use uma densidade padrão baseada em materiais similares e INDIQUE CLARAMENTE que está usando uma estimativa
        
        DENSIDADES CONHECIDAS:
        {materiais_conhecidos}
        
        Forneça sua resposta EXATAMENTE neste formato:
        Peso: [número em kg, use ponto como separador decimal]
        Memorial: [sua explicação detalhada incluindo a densidade utilizada e cálculos]
        Forma de comercialização: [forneça como esse material é usualmente comercializado]
        Nova densidade: [se você usou uma densidade que não está na lista acima, forneça o valor aqui no formato número kg/m³, caso contrário deixe em branco]

        Exemplo de resposta correta:
        Peso: 5.00
        Memorial: Para madeira compensada, considerando densidade média de 0.5 kg/dm³ e uma quantidade de 10 dm³ e a unidade de dm³, o peso total é 0.5 × 10 = 5.00 kg. O resultado SEMPRE será em kg.
        Forma de comercialização: Usualmente comercializado em placas 1m x 1m.
        Nova densidade: 
        
        Exemplo com grandes quantidades:
        Peso: 726795.00
        Memorial: Para brita, considerando densidade de 1500 kg/m³ e uma quantidade de 484.53 m³, o peso total é 1500 × 484.53 = 726795.00 kg. NUNCA divida por 1000 ou converta para toneladas. O resultado SEMPRE será em kg.
        Forma de comercialização: Usualmente comercializado em metros cúbicos.
        Nova densidade:
        
        Exemplo para tubos:
        Peso: 157.08
        Memorial: Para tubo de aço com diâmetro 33.7mm, espessura 2.25mm e altura 6000mm: Volume = 2×π×(33.7/2)×2.25×6000 = 0.02 m³. Com densidade do aço 7850 kg/m³: 7850 × 0.02 = 157.08 kg.
        Forma de comercialização: Usualmente comercializado por metro linear.
        Nova densidade:
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
                    "model": "x-ai/grok-4-fast",  # Grok-4-Fast - modelo mais avançado
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
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise Exception(f"Erro 404: Endpoint não encontrado. Verifique se a URL da API está correta: {e.response.url}")
            elif e.response.status_code == 401:
                raise Exception("Erro 401: API Key inválida ou expirada. Verifique sua chave OpenRouter.")
            elif e.response.status_code == 403:
                raise Exception("Erro 403: Acesso negado. Verifique se sua conta OpenRouter tem créditos.")
            else:
                raise Exception(f"Erro HTTP {e.response.status_code}: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Erro na chamada da API: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Erro ao decodificar resposta JSON: {str(e)}")
        except Exception as e:
            raise Exception(f"Erro inesperado: {str(e)}")

        # Usa a nova função de parsing mais robusta
        resultado = extrair_resposta_ia(resposta_completa)
        
        peso = resultado['peso']
        memorial = resultado['memorial']
        forma_comercializacao = resultado['forma_comercializacao']
        nova_densidade_texto = resultado['nova_densidade']
        nova_densidade_valor = ""
        
        # Valida se o peso foi extraído corretamente
        if peso is None:
            raise ValueError(f"Não foi possível extrair o peso da resposta da IA")
        
        # Processa nova densidade se fornecida
        if nova_densidade_texto and nova_densidade_texto.strip() != "":
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
                    
                    # Verifica se o material já existe no glossário
                    glossario_atual = carregar_glossario_densidades()
                    material_nome_normalizado = material_nome.lower().strip()
                    
                    if material_nome_normalizado in glossario_atual:
                        # Material já existe, verifica se a densidade é diferente
                        densidade_existente = glossario_atual[material_nome_normalizado]["densidade"]
                        if abs(densidade_existente - nova_densidade) > 0.1:  # Tolerância de 0.1 kg/m³
                            st.info(f"ℹ️ Material '{material_nome}' já existe com densidade {densidade_existente} kg/m³. Nova densidade {nova_densidade} kg/m³ ignorada.")
                        # Se for a mesma densidade, não faz nada (evita spam)
                    else:
                        # Material novo, adiciona ao glossário
                        atualizar_glossario_densidades(
                            material_nome, 
                            nova_densidade, 
                            "kg/m³", 
                            descricao
                        )
                        st.success(f"✨ Nova densidade adicionada ao glossário: {material_nome} = {nova_densidade} kg/m³")
            except Exception as e:
                st.warning(f"Não foi possível processar a nova densidade: {e}")

        return peso, memorial, forma_comercializacao, nova_densidade_valor

    except Exception as e:
        st.error(f"Erro ao calcular peso: {e}")
        return None, None, None, None

def detectar_estrutura_planilha(arquivo_carregado):
    """
    Detecta automaticamente a estrutura da planilha para encontrar as colunas corretas.
    """
    try:
        # Lê as primeiras 20 linhas para análise
        df_analise = pd.read_excel(arquivo_carregado, header=None, nrows=20)
        
        # Procura por palavras-chave nas células
        descricao_col = None
        unidade_col = None
        quantidade_col = None
        data_start_row = None
        
        for row_idx in range(len(df_analise)):
            for col_idx in range(len(df_analise.columns)):
                cell_value = str(df_analise.iloc[row_idx, col_idx]).lower()
                
                # Procura pela coluna de descrição
                if 'descrição' in cell_value or 'descricao' in cell_value:
                    descricao_col = col_idx
                    data_start_row = row_idx + 1
                
                # Procura pela coluna de unidade
                if 'und' in cell_value or 'unidade' in cell_value:
                    unidade_col = col_idx
                
                # Procura pela coluna de quantidade
                if 'quantidade' in cell_value:
                    quantidade_col = col_idx
        
        # Se não encontrou pelos headers, usa valores padrão baseados na análise
        if descricao_col is None:
            descricao_col = 3  # Coluna D
        if unidade_col is None:
            unidade_col = 5    # Coluna F
        if quantidade_col is None:
            quantidade_col = 6 # Coluna G
        if data_start_row is None:
            data_start_row = 5 # Linha 6 (índice 5)
        
        return {
            'descricao_col': descricao_col,
            'unidade_col': unidade_col,
            'quantidade_col': quantidade_col,
            'data_start_row': data_start_row,
            'columns': [descricao_col, unidade_col, quantidade_col]
        }
    
    except Exception as e:
        st.warning(f"Erro ao detectar estrutura da planilha: {e}. Usando configuração padrão.")
        return {
            'descricao_col': 3,
            'unidade_col': 5,
            'quantidade_col': 6,
            'data_start_row': 5,
            'columns': [3, 5, 6]
        }

def principal():
    st.title('Calculadora de Pesos de Insumos')
    
    # Valida configuração da API
    if not validar_configuracao_api():
        st.stop()
    
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
                st.rerun()
        
        # Informações sobre filtros
        st.write("### ⏰⚡ Unidades Ignoradas (Tempo/Energia)")
        st.info("O sistema automaticamente ignora itens com unidades de tempo e energia:")
        col1, col2 = st.columns(2)
        with col1:
            st.text("🕐 Tempo:")
            st.text("h, hrs, dia, dias, mês, ano, min, seg, semana")
        with col2:
            st.text("⚡ Energia:")
            st.text("KWH, HP, KW, W, VA, KVA, CV")
    
    # Upload do arquivo
    arquivo_carregado = st.file_uploader("Escolha uma planilha de insumos", type=['xlsx', 'xls'])
    
    if arquivo_carregado is not None:
        try:
            # Detecta a estrutura da planilha
            estrutura = detectar_estrutura_planilha(arquivo_carregado)
            
            st.info(f"📊 Estrutura detectada: Descrição=Col {chr(65+estrutura['descricao_col'])}, Unidade=Col {chr(65+estrutura['unidade_col'])}, Quantidade=Col {chr(65+estrutura['quantidade_col'])}, Dados a partir da linha {estrutura['data_start_row']+1}")
            
            # Lê o arquivo Excel com a estrutura detectada
            df = pd.read_excel(
                arquivo_carregado,
                skiprows=estrutura['data_start_row'],  # Pula as linhas de cabeçalho
                usecols=estrutura['columns'],  # Usa as colunas detectadas
                names=['Descrição', 'Unidade', 'Quantidade'],  # Renomeia colunas
                decimal=','  # Especifica que vírgula é o separador decimal no Excel
            )
            
            # Remove linhas completamente vazias
            df = df.dropna(how='all')
            
            # Mostra estatísticas das unidades
            st.info(f"📊 Total de itens carregados: {len(df)}")
            
            # Filtra unidades de tempo e energia ANTES de processar
            unidades_filtradas = df[df['Unidade'].apply(eh_unidade_tempo_ou_energia)]
            
            if not unidades_filtradas.empty:
                st.warning(f"⏰⚡ Ignorando {len(unidades_filtradas)} itens com unidades de tempo/energia:")
                with st.expander("Ver itens ignorados"):
                    for _, linha in unidades_filtradas.iterrows():
                        st.text(f"  • {linha['Descrição'][:60]}... ({linha['Unidade']})")
            
            # Separa itens para processamento (sem remover da planilha final)
            df_para_processar = df[~df['Unidade'].apply(eh_unidade_tempo_ou_energia)]
            df_ignorados = df[df['Unidade'].apply(eh_unidade_tempo_ou_energia)]
            
            if df_para_processar.empty:
                st.error("❌ Nenhum item válido encontrado para cálculo de peso!")
                return
            
            # Mostra resultado do filtro
            if len(df_ignorados) > 0:
                st.success(f"✅ Processando {len(df_para_processar)} itens ({len(df_ignorados)} itens de tempo/energia serão mantidos na planilha sem cálculo)")
            else:
                st.success(f"✅ Processando {len(df_para_processar)} itens (nenhuma unidade de tempo/energia encontrada)")
            
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
            
            # Calcula pesos apenas para itens válidos
            total_itens = len(df_para_processar)
            contador_processados = 0
            
            # Preenche itens ignorados com informações explicativas
            for indice in df_ignorados.index:
                df.at[indice, 'Peso (kg)'] = "N/A (Serviço/Tempo)"
                df.at[indice, 'Memorial'] = f"Item ignorado: unidade '{df.at[indice, 'Unidade']}' refere-se a tempo/energia, não a material físico"
                df.at[indice, 'Forma de Comercialização'] = "Serviço"
                df.at[indice, 'Nova Densidade'] = ""
            
            for indice, linha in df_para_processar.iterrows():
                descricao = linha['Descrição']
                quantidade = linha['Quantidade']
                unidade = linha['Unidade']
                
                if pd.notna(descricao) and pd.notna(quantidade) and pd.notna(unidade):
                    try:
                        # Calcula peso
                        peso, memorial, forma_comercializacao, nova_densidade = calcular_peso_com_llm(descricao, quantidade, unidade)
                        
                        # Atualiza dataframe
                        df.at[indice, 'Peso (kg)'] = peso
                        df.at[indice, 'Memorial'] = memorial
                        df.at[indice, 'Forma de Comercialização'] = forma_comercializacao
                        df.at[indice, 'Nova Densidade'] = nova_densidade
                        
                        st.success(f"✅ Processado: {descricao[:50]}...")
                        
                    except Exception as e:
                        st.error(f"❌ Erro ao processar '{descricao[:50]}...': {e}")
                        # Continua processando os outros itens
                
                # Atualiza progresso corretamente
                contador_processados += 1
                progresso = min(contador_processados / total_itens, 1.0)  # Garante que não passe de 1.0
                barra_progresso.progress(progresso)
                
                # Salvamento automático a cada 10 itens
                if contador_processados % 10 == 0:
                    try:
                        csv_backup = df.to_csv(index=False, decimal='.')
                        st.info(f"💾 Backup automático: {contador_processados}/{total_itens} itens processados")
                    except Exception as e:
                        st.warning(f"Erro no backup: {e}")
            
            # Finaliza barra de progresso
            barra_progresso.progress(1.0)
            
            # Exibe dataframe atualizado
            st.subheader('Planilha com Pesos Calculados')
            st.dataframe(df)
            
            # Opção de download sempre disponível
            try:
                csv = df.to_csv(index=False, decimal='.')
                
                # Estatísticas do processamento
                itens_processados = df['Peso (kg)'].notna().sum()
                st.info(f"📊 Processamento concluído: {itens_processados}/{len(df)} itens calculados")
                
                # Botão de download principal
                st.download_button(
                    label="📥 Baixar Planilha Completa (CSV)",
                    data=csv,
                    file_name=f'insumos_com_pesos_{pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")}.csv',
                    mime='text/csv',
                    type="primary"
                )
                
                # Botão de download apenas dos itens processados
                df_processados = df[df['Peso (kg)'].notna()]
                if len(df_processados) > 0:
                    csv_processados = df_processados.to_csv(index=False, decimal='.')
                    st.download_button(
                        label="📥 Baixar Apenas Itens Calculados (CSV)",
                        data=csv_processados,
                        file_name=f'insumos_calculados_{pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")}.csv',
                        mime='text/csv'
                    )
                
            except Exception as e:
                st.error(f"Erro ao preparar download: {e}")
                # Download de emergência
                try:
                    csv_emergencia = df.to_csv(index=False)
                    st.download_button(
                        label="🚨 Download de Emergência",
                        data=csv_emergencia,
                        file_name='backup_emergencia.csv',
                        mime='text/csv'
                    )
                except:
                    st.error("Não foi possível criar arquivo de backup")
            
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
            
            # Tenta salvar o que foi processado até agora
            try:
                if 'df' in locals() and not df.empty:
                    st.warning("🚨 Tentando salvar dados processados até o momento do erro...")
                    
                    # Conta itens processados
                    if 'Peso (kg)' in df.columns:
                        itens_salvos = df['Peso (kg)'].notna().sum()
                        st.info(f"📊 Itens processados antes do erro: {itens_salvos}/{len(df)}")
                    
                    # Download de emergência
                    csv_emergencia = df.to_csv(index=False, decimal='.')
                    st.download_button(
                        label="🚨 Baixar Dados Parciais (Emergência)",
                        data=csv_emergencia,
                        file_name=f'backup_parcial_{pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")}.csv',
                        mime='text/csv',
                        type="secondary"
                    )
                    
                    st.success("✅ Backup de emergência disponível para download!")
                    
            except Exception as backup_error:
                st.error(f"Não foi possível criar backup de emergência: {backup_error}")

if __name__ == "__main__":
    principal()
