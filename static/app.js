"use strict";

const chat      = document.getElementById("chat");
const input     = document.getElementById("input");
const btnEnviar = document.getElementById("btn-enviar");
const indicador = document.getElementById("processando");

const historico = [];

// ── Helpers de UI ──────────────────────────────────────────

function mostrarIndicadorProcessando() {
    indicador.classList.remove("oculto");
    indicador.setAttribute("aria-hidden", "false");
    chat.appendChild(indicador);
    indicador.scrollIntoView({ behavior: "smooth" });
}

function esconderIndicadorProcessando() {
    indicador.classList.add("oculto");
    indicador.setAttribute("aria-hidden", "true");
}

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

// ── Renderização de partes ─────────────────────────────────

function renderizarResposta(parts) {
    const balao = document.createElement("div");
    balao.className = "mensagem ia";

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
            fetch("/api/executar", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ codigo: part.conteudo }),
            })
            .then(r => r.json())
            .then(r => {
                const pre = document.createElement("pre");
                pre.className = "bloco-python";
                pre.textContent = r.saida ?? r.erro;
                balao.appendChild(pre);
                pre.scrollIntoView({ behavior: "smooth" });
            });
        }
    }

    chat.appendChild(balao);
    balao.scrollIntoView({ behavior: "smooth" });
}

// ── Envio de mensagem ──────────────────────────────────────

async function enviarMensagem() {
    const texto = input.value.trim();
    if (!texto) return;

    btnEnviar.disabled = true;
    adicionarMensagemUsuario(texto);
    mostrarIndicadorProcessando();
    input.value = "";

    historico.push({ role: "user", content: texto });

    try {
        const resp = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                mensagem: texto,
                historico: historico.slice(-10),
            }),
        });

        const data = await resp.json();
        esconderIndicadorProcessando();

        if (data.parts) {
            renderizarResposta(data.parts);
            historico.push({ role: "assistant", content: JSON.stringify(data.parts) });
        } else {
            renderizarErro(data.erro || "Erro desconhecido");
        }
    } catch (err) {
        esconderIndicadorProcessando();
        renderizarErro("Falha na conexão com o servidor.");
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
