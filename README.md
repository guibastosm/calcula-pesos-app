# Calcula Pesos App

Uma aplicação Streamlit para calcular pesos de materiais e insumos de construção civil utilizando IA.

## Descrição

Esta aplicação utiliza o GPT da OpenAI para auxiliar no cálculo de pesos de materiais de construção, convertendo diferentes unidades de medida para quilogramas (kg). É especialmente útil para profissionais da construção civil que precisam fazer estimativas de peso para transporte e logística.

## Funcionalidades

- Conversão de diferentes unidades para kg
- Suporte para diversos materiais de construção
- Interface intuitiva usando Streamlit
- Processamento inteligente usando GPT para análise de descrições de materiais

## Requisitos

- Python 3.8+
- Streamlit
- OpenAI API Key
- Pandas

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/guibastosm/calcula-pesos-app.git
cd calcula-pesos-app
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure as variáveis de ambiente:
   - Copie o arquivo `.env.example` para `.env`
   - Adicione sua chave da API OpenAI no arquivo `.env`

## Como Usar

1. Inicie a aplicação:
```bash
streamlit run app.py
```

2. Acesse a aplicação no seu navegador (geralmente em `http://localhost:8501`)

3. Insira os dados do material:
   - Descrição do material
   - Quantidade
   - Unidade de medida

## Contribuição

Contribuições são bem-vindas! Por favor, sinta-se à vontade para submeter pull requests.

## Licença

Este projeto está sob a licença MIT.
