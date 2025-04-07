import streamlit as st
import pandas as pd
from openai import OpenAI
import os
from dotenv import load_dotenv
import re

# Carrega variáveis de ambiente
load_dotenv()

# Configura API OpenAI
cliente = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

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
            return peso, memorial
            
        # Se não for unidade básica, usa a API OpenAI
        prompt = f"""
        Calcule o peso em kg para o seguinte insumo:
        - Descrição: {descricao}
        - Quantidade: {quantidade}
        - Unidade de Medida: {unidade}

        Pernse de maneira passo a passo.

        Forneça sua resposta EXATAMENTE neste formato:
        Peso: [número em kg, use ponto como separador decimal]
        Memorial: [sua explicação]
        Forma de comercialização: [forneça como esse material é usualmente comercializado]

        Exemplo de resposta correta:
        Peso: 5 kg
        Memorial: Para madeira compensada, considerando densidade média de 0.5 kg/dm³ e uma quantidade de 10 dm³ e a unidade de dm³, o peso total é 0.5 (kg/dm3) * 10 (dm³) = 5 kg. O resultado SEMPRE será em kg.
        Forma de comercialização: Usualmente comercializado em placas 1m x 1m.

        Outro exemplo:
        Peso: 850 kg
        Memorial: Para o saco de cimento, considerando densidade média de 42,5 kg/saco e uma quantidade de 20 sacos e a unidade em saco, o peso total é 42.5 (kg/saco) * 20 (saco) = 850 kg. O resultado SEMPRE será em kg.
        Forma de comercialização: Usualmente comercializado em sacos de 42,5 kg.
        """

        # Chama API OpenAI
        resposta = cliente.chat.completions.create(
            model="gpt-4o-2024-11-20",
            messages=[
                {"role": "system", "content": "Você é um assistente técnico especializado em calcular pesos de materiais de construção. Use SEMPRE ponto como separador decimal, nunca vírgula. "},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0
        )

        # Extrai a resposta
        resposta_completa = resposta.choices[0].message.content.strip()
        
        # Divide a resposta em peso e memorial
        linhas = resposta_completa.split('\n')
        texto_peso = linhas[0].split(':')[1].strip()
        
        # Limpa e converte o peso
        peso = limpar_numero(texto_peso)
        if peso is None:
            raise ValueError(f"Não foi possível converter o peso: {texto_peso}")
            
        memorial = '\n'.join(linhas[1:])

        return peso, memorial

    except Exception as e:
        st.error(f"Erro ao calcular peso: {e}")
        return None, None

def principal():
    st.title('Calculadora de Pesos de Insumos')
    
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
            
            # Novas colunas para peso e memorial
            df['Peso (kg)'] = None
            df['Memorial de Cálculo'] = None
            
            # Calcula pesos
            for indice, linha in df.iterrows():
                descricao = linha['Descrição']
                quantidade = linha['Quantidade']
                unidade = linha['Unidade']
                
                if pd.notna(descricao) and pd.notna(quantidade) and pd.notna(unidade):
                    # Calcula peso
                    peso, memorial = calcular_peso_com_llm(descricao, quantidade, unidade)
                    
                    # Atualiza dataframe
                    df.at[indice, 'Peso (kg)'] = peso
                    df.at[indice, 'Memorial de Cálculo'] = memorial
                
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
            
            # Memorial detalhado
            st.subheader('Memorials de Cálculo')
            for indice, linha in df.iterrows():
                if pd.notna(linha.get('Memorial de Cálculo')):
                    st.write(f"**Item {indice + 1}:**")
                    st.write(f"Descrição: {linha['Descrição']}")
                    peso = linha.get('Peso (kg)')
                    if pd.notna(peso):
                        st.write(f"Peso: {peso:.2f} kg")
                    else:
                        st.write("Peso: N/A kg")
                    st.write(f"Memorial: {linha.get('Memorial de Cálculo', 'Não calculado')}")
                    st.markdown("---")
        
        except Exception as e:
            st.error(f"Erro ao processar planilha: {e}")

if __name__ == "__main__":
    principal()
