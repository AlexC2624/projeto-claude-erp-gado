"use strict";

const chat      = document.getElementById("chat");
const input     = document.getElementById("input");
const btnEnviar = document.getElementById("btn-enviar");

const historico = [];

// ── Helpers de UI ──────────────────────────────────────────

function adicionarMensagemUsuario(texto) {
    const div = document.createElement("div");
    div.className = "mensagem usuario";
    div.textContent = texto;
    chat.appendChild(div);
    div.scrollIntoView({ behavior: "smooth" });
}

function renderizarErro(msg) {
    const div = document.createElement("div");
    div.className = "mensagem erro";
    div.textContent = "Erro: " + msg;
    chat.appendChild(div);
    div.scrollIntoView({ behavior: "smooth" });
}

// ── Renderização de parts num balão existente ──────────────

function preencherBalao(parts, balao) {
    for (const part of parts) {
        if (part.tipo === "texto") {
            const p = document.createElement("p");
            p.textContent = part.conteudo;
            balao.appendChild(p);

        } else if (part.tipo === "html") {
            const wrapper = document.createElement("div");
            wrapper.className = "bloco-html";
            wrapper.innerHTML = part.conteudo;
            balao.appendChild(wrapper);

        } else if (part.tipo === "python") {
            const pre = document.createElement("pre");
            pre.className = "bloco-python";
            pre.textContent = "Calculando…";
            balao.appendChild(pre);

            fetch("/api/executar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ codigo: part.conteudo }),
            })
            .then(r => r.json())
            .then(r => {
                pre.textContent = r.saida ?? r.erro;
                pre.scrollIntoView({ behavior: "smooth" });
            });
        }
    }
    balao.scrollIntoView({ behavior: "smooth" });
}

// Mantida para a mensagem de boas-vindas
function renderizarResposta(parts) {
    const balao = document.createElement("div");
    balao.className = "mensagem ia";
    chat.appendChild(balao);
    preencherBalao(parts, balao);
}

// ── Processamento de eventos SSE ───────────────────────────

function processarEvento(evento, balao, logArea, estado) {
    switch (evento.tipo) {

        // Modelo começou a gerar — atualiza o indicador "Pensando…"
        case "gerando": {
            estado.indicador.textContent = "Gerando resposta…";
            break;
        }

        // Token chegando em tempo real — constrói o texto progressivamente
        case "token": {
            // Remove o indicador de "Pensando/Gerando" na primeira chegada de token
            if (estado.indicador && estado.indicador.parentNode) {
                estado.indicador.remove();
                estado.indicador = null;
            }
            if (!estado.streamEl) {
                logArea.remove();
                estado.streamEl = document.createElement("p");
                estado.streamEl.className = "stream-texto";
                balao.appendChild(estado.streamEl);
            }
            estado.streamEl.textContent += evento.conteudo;
            balao.scrollIntoView({ behavior: "smooth" });
            break;
        }

        // Ferramenta começou a executar
        case "ferramenta_inicio": {
            // Remove indicador "Gerando" quando ferramentas começam
            if (estado.indicador && estado.indicador.parentNode) {
                estado.indicador.remove();
                estado.indicador = null;
            }
            const item = document.createElement("div");
            item.className = "log-item ativo";
            item.dataset.nome = evento.nome;
            item.textContent = evento.descricao || evento.nome;
            logArea.appendChild(item);
            estado.ultimoLogItem = item;
            balao.scrollIntoView({ behavior: "smooth" });
            break;
        }

        // Ferramenta concluída
        case "ferramenta_fim": {
            const ativo = logArea.querySelector(
                `.log-item.ativo[data-nome="${evento.nome}"]`
            );
            if (ativo) {
                ativo.classList.remove("ativo");
                ativo.classList.add("concluido");
            }
            break;
        }

        // Resposta final — renderiza o conteúdo completo
        case "partes": {
            // Remove texto em streaming se existia (substituído pelas partes)
            if (estado.streamEl) {
                estado.streamEl.remove();
                estado.streamEl = null;
            }
            logArea.remove();
            preencherBalao(evento.parts, balao);
            historico.push({
                role: "assistant",
                content: JSON.stringify(evento.parts),
            });
            break;
        }

        case "heartbeat":
            // keep-alive silencioso — mantém a conexão SSE viva enquanto o modelo processa
            break;

        case "erro": {
            if (estado.streamEl) estado.streamEl.remove();
            logArea.remove();
            const p = document.createElement("p");
            p.className = "erro-ia";
            p.textContent = "Erro: " + evento.mensagem;
            balao.appendChild(p);
            balao.scrollIntoView({ behavior: "smooth" });
            break;
        }
    }
}

// ── Envio de mensagem com streaming SSE ───────────────────

async function enviarMensagem() {
    const texto = input.value.trim();
    if (!texto) return;

    btnEnviar.disabled = true;
    input.value = "";

    adicionarMensagemUsuario(texto);
    historico.push({ role: "user", content: texto });

    // Balão da IA com indicador "Pensando…" imediato
    const balao = document.createElement("div");
    balao.className = "mensagem ia";

    const logArea = document.createElement("div");
    logArea.className = "ia-log";

    const indicador = document.createElement("div");
    indicador.className = "log-item ativo";
    indicador.textContent = "Pensando…";
    logArea.appendChild(indicador);

    balao.appendChild(logArea);
    chat.appendChild(balao);
    balao.scrollIntoView({ behavior: "smooth" });

    // Estado mutável compartilhado entre eventos do mesmo turn
    const estado = { indicador, streamEl: null, ultimoLogItem: null };

    try {
        const resp = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                mensagem: texto,
                historico: historico.slice(-10),
            }),
        });

        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // SSE usa \n\n como separador de eventos
            const blocos = buffer.split("\n\n");
            buffer = blocos.pop();

            for (const bloco of blocos) {
                for (const linha of bloco.split("\n")) {
                    if (!linha.startsWith("data: ")) continue;
                    try {
                        const evento = JSON.parse(linha.slice(6));
                        processarEvento(evento, balao, logArea, estado);
                    } catch (e) {
                        console.error("SSE parse error:", e, linha);
                    }
                }
            }
        }

    } catch (err) {
        if (estado.indicador?.parentNode) estado.indicador.remove();
        logArea.remove();
        renderizarErro("Falha na conexão: " + err.message);
    } finally {
        btnEnviar.disabled = false;
        input.focus();
    }
}

// ── Atalho Enter ───────────────────────────────────────────

input.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        enviarMensagem();
    }
});

// ── Boas-vindas ────────────────────────────────────────────

window.addEventListener("DOMContentLoaded", () => {
    renderizarResposta([{
        tipo: "texto",
        conteudo:
            "Olá! Sou o assistente de gestão rural. Posso ajudar com consultas sobre " +
            "rebanhos, estoque de insumos, controle financeiro e muito mais. " +
            "Como posso ajudar hoje?",
    }]);
    input.focus();
});
