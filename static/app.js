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

function processarEvento(evento, balao, logArea) {
    switch (evento.tipo) {

        case "ferramenta_inicio": {
            const item = document.createElement("div");
            item.className = "log-item ativo";
            item.dataset.nome = evento.nome;
            item.textContent = evento.descricao || evento.nome;
            logArea.appendChild(item);
            logArea._atual = item;
            balao.scrollIntoView({ behavior: "smooth" });
            break;
        }

        case "ferramenta_fim": {
            // Marca o item ativo mais recente como concluído
            const ativo = logArea.querySelector(`.log-item.ativo[data-nome="${evento.nome}"]`);
            if (ativo) {
                ativo.classList.remove("ativo");
                ativo.classList.add("concluido");
            }
            break;
        }

        case "partes": {
            logArea.remove();
            preencherBalao(evento.parts, balao);
            historico.push({ role: "assistant", content: JSON.stringify(evento.parts) });
            break;
        }

        case "erro": {
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

    // Cria balão da IA com área de log imediatamente
    const balao = document.createElement("div");
    balao.className = "mensagem ia";

    const logArea = document.createElement("div");
    logArea.className = "ia-log";
    const dot = document.createElement("div");
    dot.className = "log-item ativo";
    dot.textContent = "Pensando…";
    logArea.appendChild(dot);
    balao.appendChild(logArea);
    chat.appendChild(balao);
    balao.scrollIntoView({ behavior: "smooth" });

    try {
        const resp = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                mensagem: texto,
                historico: historico.slice(-10),
            }),
        });

        if (!resp.ok) {
            throw new Error(`HTTP ${resp.status}`);
        }

        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // Processa linhas completas (SSE usa \n\n como separador de eventos)
            const blocos = buffer.split("\n\n");
            buffer = blocos.pop(); // guarda linha incompleta

            for (const bloco of blocos) {
                for (const linha of bloco.split("\n")) {
                    if (!linha.startsWith("data: ")) continue;
                    try {
                        const evento = JSON.parse(linha.slice(6));
                        // Remove o "Pensando…" na primeira ferramenta/parte real
                        if (dot.parentNode) dot.remove();
                        processarEvento(evento, balao, logArea);
                    } catch (e) {
                        console.error("SSE parse error:", e, linha);
                    }
                }
            }
        }

    } catch (err) {
        logArea.remove();
        renderizarErro("Falha na conexão com o servidor: " + err.message);
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
