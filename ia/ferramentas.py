TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consulta",
            "description": (
                "Busca dados reais do banco de dados. Use SEMPRE que precisar de "
                "qualquer número, lista ou valor. Nunca estime — consulte."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": 'Nome da tabela: "produto", "animal" ou "transacao"',
                    },
                    "col": {
                        "type": "string",
                        "description": 'Coluna a consultar (ex: "quantidade", "valor", "id")',
                    },
                    "fun": {
                        "type": "string",
                        "enum": ["soma", "contagem", "media", "lista", "maximo", "minimo"],
                        "description": "Função de agregação ou listagem",
                    },
                },
                "required": ["table", "col", "fun"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cadastra",
            "description": (
                "Insere novo registro no banco. Use quando o usuário pedir para "
                "adicionar, registrar ou criar algo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Tabela de destino: produto, animal ou transacao",
                    },
                    "dados": {
                        "type": "object",
                        "description": "Campos e valores do novo registro",
                    },
                },
                "required": ["table", "dados"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "atualiza",
            "description": "Atualiza um registro existente pelo id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Nome da tabela",
                    },
                    "id": {
                        "type": "integer",
                        "description": "ID do registro a atualizar",
                    },
                    "dados": {
                        "type": "object",
                        "description": "Campos a atualizar com os novos valores",
                    },
                },
                "required": ["table", "id", "dados"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "deleta",
            "description": "Remove um registro pelo id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table": {
                        "type": "string",
                        "description": "Nome da tabela",
                    },
                    "id": {
                        "type": "integer",
                        "description": "ID do registro a remover",
                    },
                },
                "required": ["table", "id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "responda",
            "description": (
                "Envia a resposta final ao usuário. Chame SOMENTE quando tiver "
                "TODOS os dados necessários. Nunca chame antes de consultar os valores."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "parts": {
                        "type": "array",
                        "description": "Lista ordenada de blocos de conteúdo",
                        "items": {
                            "type": "object",
                            "properties": {
                                "tipo": {
                                    "type": "string",
                                    "enum": ["texto", "html", "python"],
                                    "description": "Tipo do bloco",
                                },
                                "conteudo": {
                                    "type": "string",
                                    "description": "Conteúdo do bloco",
                                },
                            },
                            "required": ["tipo", "conteudo"],
                        },
                    }
                },
                "required": ["parts"],
            },
        },
    },
]
