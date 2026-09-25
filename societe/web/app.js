/* Interface de la simulation de société. Tout l'état vient du serveur ;
   la page ne fait que l'afficher et renvoyer les décisions du joueur. */

let S = null;             // dernier instantané reçu
let filtre = "tout";
let seulementRealisables = true;
let auto = null;          // intervalle du mode « laisser filer »

const $ = (s) => document.querySelector(s);
const el = (n, a = {}, t) => {
  const e = document.createElementNS("http://www.w3.org/2000/svg", n);
  for (const k in a) e.setAttribute(k, a[k]);
  if (t != null) e.textContent = t;
  return e;
};
const nb = (v, d = 0) => new Intl.NumberFormat("fr-FR", { maximumFractionDigits: d }).format(v);

/* ---------------- réseau ---------------- */
async function api(route, corps = {}) {
  const r = await fetch(route, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corps),
  });
  const d = await r.json();
  if (!r.ok || d.erreur) { montrerErreur(d.erreur || "erreur"); return null; }
  S = d;
  rendre();
  return d;
}
function montrerErreur(texte) {
  const e = $("#erreur");
  e.textContent = texte;
  e.hidden = false;
  clearTimeout(montrerErreur._t);
  montrerErreur._t = setTimeout(() => { e.hidden = true; }, 3200);
}

/* ---------------- rendu ---------------- */
function rendre() {
  if (!S || !S.etat) return;
  $("#accueil").hidden = true;
  $("#jeu").hidden = false;
  rendreBarre();
  rendrePersonnes();
  rendreLieu();
  rendreChantier();
  rendreCatalogue();
  rendreRessources();
  rendreDemographie();
  rendreGraphiques();
  rendreJournal();
  if (S.etat.termine) arreterAuto();
}

function rendreBarre() {
  const e = S.etat, d = e.derive, a = S.apercu;
  $("#b-date").textContent = d.date;
  $("#b-meteo").textContent = `${e.meteo.description}, ${nb(e.meteo.temperature, 1)} °C` +
    (e.meteo.pluie > 0 ? ` · ${nb(e.meteo.pluie, 1)} mm` : "");
  const seuil = (v, bas, tresbas) => v <= tresbas ? "alerte" : (v <= bas ? "prudence" : "");
  const ind = [
    ["Habitants", nb(d.population), ""],
    ["Vivres", `${nb(a.autonomie_nourriture_jours, 1)} j`, seuil(a.autonomie_nourriture_jours, 10, 3)],
    ["Eau", a.eau_deficit > 0 ? `−${nb(a.eau_deficit)} L/j` : `${nb(a.autonomie_eau_jours, 1)} j`,
      a.eau_deficit > 0 ? (a.autonomie_eau_jours < 2 ? "alerte" : "prudence")
        : seuil(a.autonomie_eau_jours, 4, 1)],
    ["Moral", nb(d.moral), seuil(d.moral, 40, 22)],
    ["Santé", nb(d.sante), seuil(d.sante, 60, 35)],
    ["Cohésion", nb(e.cohesion * 100), seuil(e.cohesion * 100, 55, 35)],
    ["Coordination", `${nb(a.coordination * 100)} %`, seuil(a.coordination * 100, 75, 55)],
    ["Abri", `${nb(a.abri)}/${nb(d.population)}`, a.abri < d.population ? "prudence" : ""],
  ];
  $("#b-indicateurs").innerHTML = ind.map(([t, v, c]) =>
    `<div class="ind"><div class="et">${t}</div><div class="va ${c}">${v}</div></div>`).join("");
}

function couleurJauge(v) {
  return v >= 60 ? "var(--bon)" : v >= 30 ? "var(--attention)" : "var(--grave)";
}

function rendrePersonnes() {
  const e = S.etat;
  $("#p-compte").textContent = e.personnes.length;
  const taches = S.referentiel.taches;
  $("#p-liste").innerHTML = e.personnes.map((p) => {
    const jauge = (nom, v) => `<div class="jauge"><span>${nom}</span>
      <span class="piste"><i style="width:${Math.max(2, v)}%;background:${couleurJauge(v)}"></i></span>
      <span>${nb(v)}</span></div>`;
    const spec = Object.entries(p.competences).sort((a, b) => b[1] - a[1])[0];
    const options = Object.entries(taches).map(([k, v]) =>
      `<option value="${k}" ${p.tache === k ? "selected" : ""}>${v}</option>`).join("");
    const enfant = p.age < 14;
    const nomDe = (id) => (e.personnes.find((q) => q.id === id) || {}).nom;
    const etiquettes = [];
    if (enfant) etiquettes.push(`<span class="etiq enfant">${p.age < 6 ? "petite enfance" : "enfant"}</span>`);
    if (p.grossesse != null) etiquettes.push(
      `<span class="etiq grossesse">enceinte — ${Math.max(0, 274 - p.grossesse)} j</span>`);
    if (p.partenaire) etiquettes.push(`<span class="etiq">avec ${nomDe(p.partenaire) || "?"}</span>`);
    const vivants = p.enfants.filter((id) => nomDe(id));
    if (vivants.length) etiquettes.push(
      `<span class="etiq">${vivants.length} enfant${vivants.length > 1 ? "s" : ""}</span>`);
    if (p.nee_ici) etiquettes.push(`<span class="etiq">né${p.sexe === "f" ? "e" : ""} ici</span>`);
    const risque = (S.apercu.risques || {})[p.id];
    return `<div class="personne">
      <div class="tete"><span class="nom">${p.nom}</span>
        <span class="meta" title="risque de décès dans l'année : ${risque ?? "?"} %">${p.age} ans ·
          ${enfant ? p.classe_age || "enfant" : `${spec[0]} ${Math.round(spec[1] * 100)} %`}</span></div>
      <div class="jauges">${jauge("énergie", p.energie)}${jauge("santé", p.sante)}${jauge("moral", p.moral)}</div>
      ${etiquettes.length ? `<div class="famille">${etiquettes.join("")}</div>` : ""}
      <select data-personne="${p.id}" ${enfant ? "disabled" : ""}>${options}</select>
      ${p.tache === "construction" && !e.chantier
        ? `<div class="avert">aucun chantier ouvert : cette journée est perdue</div>` : ""}
      ${p.histoire ? `<div class="histoire">« ${p.histoire} »</div>` : ""}
    </div>`;
  }).join("") || `<p class="vide">Plus personne ici.</p>`;

  $("#p-liste").querySelectorAll("select").forEach((s) => {
    s.onchange = () => api("/api/affectation", { id: +s.dataset.personne, tache: s.value });
  });

  const cap = S.apercu.capacite_gouvernance;
  const places = S.apercu.abri - e.personnes.length;
  const notes = [];
  notes.push(e.personnes.length > cap
    ? `Au-delà de ${cap} personnes, la coordination se perd : il faut des lieux et des règles communes.`
    : `Coordination tenable jusqu'à ${cap} personnes (${e.gouvernance}).`);
  notes.push(places > 0 ? `${places} place${places > 1 ? "s" : ""} libre${places > 1 ? "s" : ""} à l'abri.`
    : `Plus une place à l'abri : chaque arrivée dégrade la santé et le moral.`);
  notes.push(`${nb(S.apercu.autonomie_nourriture_jours, 1)} jours de vivres d'avance.`);
  $("#p-note").textContent = notes.join(" ");
}

const COULEUR_PARCELLE = {
  friche: "var(--texte-3)", foret: "var(--s3)", potager: "var(--s4)",
  verger: "var(--s2)", pature: "var(--s5)", bati: "var(--texte-2)", eau: "var(--s1)",
};

function rendreLieu() {
  const e = S.etat, t = e.territoire;
  const amen = e.derive.hectares_amenages;
  $("#c-territoire").textContent =
    `${nb(t.km2)} km² de territoire. ${nb(amen, 1)} hectares aménagés — ` +
    `soit ${(e.derive.part_amenagee * 100).toExponential(1).replace(".", ",")} % du total.`;

  const svg = $("#c-carte");
  svg.textContent = "";
  const groupes = {};
  for (const p of t.parcelles) {
    if (!groupes[p.type]) groupes[p.type] = { ha: 0, maturite: 0, n: 0 };
    groupes[p.type].ha += p.hectares;
    groupes[p.type].maturite += p.maturite * p.hectares;
    groupes[p.type].n++;
  }
  const entrees = Object.entries(groupes).sort((a, b) => b[1].ha - a[1].ha);
  const totalHa = entrees.reduce((s, [, g]) => s + g.ha, 0) || 1;
  // cases de taille égale : la surface se lit sur la barre, pas sur la case
  const colonnes = Math.min(4, Math.max(2, Math.ceil(Math.sqrt(entrees.length))));
  const lignes = Math.ceil(entrees.length / colonnes) || 1;
  const ecart = 8, L = 600, H = 260;
  const largeur = (L - ecart * (colonnes + 1)) / colonnes;
  const hauteur = Math.min(110, (H - ecart * (lignes + 1)) / lignes);
  svg.setAttribute("viewBox", `0 0 ${L} ${ecart + lignes * (hauteur + ecart)}`);

  entrees.forEach(([type, g], i) => {
    const cx = ecart + (i % colonnes) * (largeur + ecart);
    const cy = ecart + Math.floor(i / colonnes) * (hauteur + ecart);
    const mat = g.maturite / Math.max(g.ha, 1e-9);
    const couleur = COULEUR_PARCELLE[type] || "var(--texte-3)";
    const r = el("rect", { x: cx, y: cy, width: largeur, height: hauteur, rx: 10,
      fill: couleur, opacity: type === "friche" ? 0.12 : 0.18,
      stroke: couleur, "stroke-width": 1.5, "stroke-opacity": 0.5 });
    r.addEventListener("pointermove", (ev) => infobulle(
      `<b>${S.referentiel.types_parcelle[type] || type}</b><br>${nb(g.ha, 1)} ha` +
      ` — ${nb((g.ha / totalHa) * 100)} % du lieu` +
      (mat < 0.99 ? `<br>maturité ${Math.round(mat * 100)} %` : "")
      + (g.n > 1 ? `<br>${g.n} parcelles` : ""), ev));
    r.addEventListener("pointerleave", cacherInfobulle);
    svg.append(r);
    svg.append(el("text", { x: cx + 12, y: cy + 24, fill: "var(--texte)",
      "font-size": 13, "font-weight": 600 }, type));
    svg.append(el("text", { x: cx + 12, y: cy + 42, fill: "var(--texte-2)", "font-size": 12 },
      `${nb(g.ha, 1)} ha${mat < 0.99 ? ` · ${Math.round(mat * 100)} % mûr` : ""}`));
    // barre de proportion
    svg.append(el("rect", { x: cx + 12, y: cy + hauteur - 20, width: largeur - 24, height: 5,
      rx: 3, fill: "var(--bordure)" }));
    svg.append(el("rect", { x: cx + 12, y: cy + hauteur - 20,
      width: Math.max(3, (g.ha / totalHa) * (largeur - 24)), height: 5, rx: 3, fill: couleur }));
  });

  const noms = S.chantiers.reduce((m, c) => (m[c.cle] = c.nom, m), {});
  $("#c-batiments").innerHTML = Object.entries(e.batiments).map(([k, n]) =>
    `<span class="chip">${noms[k] || k}${n > 1 ? ` ×${n}` : ""}</span>`).join("")
    || `<span class="chip">rien de construit</span>`;
}

function rendreChantier() {
  const c = S.etat.chantier;
  const bloc = $("#c-chantier");
  if (!c) {
    bloc.innerHTML = `<p class="vide">Aucun chantier en cours. Les personnes affectées à
      « travailler sur le chantier » ne produisent rien tant que vous n'en ouvrez pas un.</p>`;
    return;
  }
  const reste = Math.max(0, c.travail_requis - c.travail_fait);
  bloc.innerHTML = `<h3>${c.nom}</h3>
    <div class="barre-progres"><i style="width:${(c.avancement ?? c.travail_fait / c.travail_requis) * 100}%"></i></div>
    <p class="sous">${nb(c.travail_fait, 1)} / ${nb(c.travail_requis)} jours-homme —
      il reste ${nb(reste, 1)}.</p>
    <button id="c-annuler" class="discret">Abandonner le chantier</button>`;
  $("#c-annuler").onclick = () => api("/api/annuler-chantier");
}

function rendreCatalogue() {
  const cats = ["tout", ...new Set(S.chantiers.map((c) => c.categorie))];
  $("#c-filtres").innerHTML = cats.map((c) =>
    `<button data-cat="${c}" aria-pressed="${filtre === c}">${c}</button>`).join("") +
    `<button id="c-realisables" aria-pressed="${seulementRealisables}">réalisables seulement</button>`;
  $("#c-filtres").querySelectorAll("button[data-cat]").forEach((b) => {
    b.onclick = () => { filtre = b.dataset.cat; rendreCatalogue(); };
  });
  $("#c-realisables").onclick = () => { seulementRealisables = !seulementRealisables; rendreCatalogue(); };

  const liste = S.chantiers
    .filter((c) => filtre === "tout" || c.categorie === filtre)
    .filter((c) => !seulementRealisables || (!c.bloque && !Object.keys(c.manquants).length))
    .sort((a, b) => (a.bloque - b.bloque) || a.travail - b.travail);

  if (!liste.length) {
    $("#c-catalogue").innerHTML = `<p class="vide">Rien de réalisable ici pour l'instant —
      il manque des matériaux, des prérequis ou des bras. Décochez « réalisables seulement »
      pour voir ce qui viendra plus tard.</p>`;
    return;
  }
  $("#c-catalogue").innerHTML = liste.map((c) => {
    const mats = Object.entries(c.materiaux).map(([r, q]) => `${nb(q)} ${r}`).join(", ");
    const manque = Object.entries(c.manquants).map(([r, q]) => `${nb(q, 1)} ${r}`).join(", ");
    const indispo = c.bloque || manque || S.etat.chantier;
    return `<div class="modele ${indispo ? "indispo" : ""}">
      <h3>${c.nom} ${c.construit ? `<span class="deja">×${c.construit}</span>` : ""}</h3>
      <div class="desc">${c.description}</div>
      <div class="cout">${nb(c.travail)} jours-homme${mats ? ` · ${mats}` : ""}</div>
      ${c.bloque ? `<div class="bloque">${c.raisons.join(" · ")}</div>` : ""}
      ${manque ? `<div class="manque">il manque : ${manque}</div>` : ""}
      <button data-cle="${c.cle}" ${indispo ? "disabled" : ""}>Lancer</button>
    </div>`;
  }).join("");

  $("#c-catalogue").querySelectorAll("button[data-cle]").forEach((b) => {
    b.onclick = () => api("/api/chantier", { cle: b.dataset.cle });
  });
}

function rendreRessources() {
  const s = S.etat.stocks, u = S.referentiel.ressources, a = S.apercu;
  const plafond = { eau: a.eau_max, electricite: a.elec_max };
  $("#r-liste").innerHTML = Object.entries(s).map(([k, v]) => {
    const max = plafond[k];
    const part = max ? Math.min(100, (v / max) * 100) : null;
    return `<div class="ressource ${v <= 0 ? "vide-stock" : ""}"><span>${k}${part !== null
      ? ` <span class="u">${Math.round(part)} % de ${nb(max)}</span>` : ""}</span>
      <span class="q">${nb(v, v < 10 ? 1 : 0)} <span class="u">${u[k]}</span></span></div>`;
  }).join("");
}

function courbe(svg, points, couleur, min, max) {
  if (points.length < 2) return;
  const G = 4, L = 300, H = 60;
  const x = (i) => G + (i / (points.length - 1)) * (L - 2 * G);
  const y = (v) => H - G - ((v - min) / Math.max(1e-9, max - min)) * (H - 2 * G);
  const d = points.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  svg.append(el("path", { d, fill: "none", stroke: couleur, "stroke-width": 2,
    "stroke-linejoin": "round", "stroke-linecap": "round" }));
}

function rendreGraphiques() {
  const h = S.etat.historique;
  const cible = $("#r-graphiques");
  cible.textContent = "";
  if (h.length < 3) { cible.innerHTML = `<p class="vide">Laissez passer quelques jours.</p>`; return; }
  const pas = Math.max(1, Math.floor(h.length / 160));
  const ech = h.filter((_, i) => i % pas === 0);

  const blocs = [
    { titre: "Habitants et constructions", series: [
      ["population", "var(--s1)", ech.map((p) => p.population)],
      ["bâtiments", "var(--s2)", ech.map((p) => p.batiments)]] },
    { titre: "Moral et santé", series: [
      ["moral", "var(--s4)", ech.map((p) => p.moral)],
      ["santé", "var(--s3)", ech.map((p) => p.sante)]] },
    { titre: "Réserves de vivres", series: [
      ["portions", "var(--s3)", ech.map((p) => p.nourriture)]] },
    { titre: "Naissances et décès cumulés", series: [
      ["naissances", "var(--s5)", ech.map((p) => p.naissances ?? 0)],
      ["décès", "var(--texte-3)", ech.map((p) => p.deces ?? 0)]] },
  ];
  for (const bloc of blocs) {
    const legende = document.createElement("div");
    legende.className = "legende-graph";
    legende.innerHTML = `<span style="color:var(--texte-3)">${bloc.titre}</span>` +
      bloc.series.map(([n, c]) => `<span><i style="background:${c}"></i>${n}</span>`).join("");
    cible.append(legende);
    const svg = el("svg", { viewBox: "0 0 300 60" });
    const toutes = bloc.series.flatMap(([, , v]) => v);
    const min = Math.min(0, ...toutes), max = Math.max(1, ...toutes);
    for (const [, couleur, valeurs] of bloc.series) {
      courbe(svg, valeurs, couleur, min, max);
      const derniere = valeurs[valeurs.length - 1];
      svg.append(el("text", { x: 296, y: 4 + (1 - (derniere - min) / Math.max(1e-9, max - min)) * 52 + 8,
        fill: couleur, "font-size": 10, "text-anchor": "end" }, nb(derniere, derniere < 10 ? 1 : 0)));
    }
    cible.append(svg);
  }
}

function rendreDemographie() {
  const e = S.etat, d = e.derive, a = S.apercu;
  const tuiles = [
    ["Naissances", nb(a.naissances)],
    ["Décès", nb(a.deces)],
    ["Âge moyen", nb(d.age_moyen, 1)],
    ["Âge au décès", d.esperance_vie != null ? nb(d.esperance_vie, 1) : "—"],
    ["Couples", nb(a.couples)],
    ["Personnes à charge", `${nb(d.dependance, 2)} / actif`],
  ];
  $("#d-tuiles").innerHTML = tuiles.map(([t, v]) =>
    `<div class="demo-tuile"><div class="et">${t}</div><div class="va">${v}</div></div>`).join("");

  // pyramide des âges
  const svg = $("#d-pyramide");
  svg.textContent = "";
  const p = d.pyramide || [];
  if (!p.length) return;
  const H = Math.max(60, p.length * 18 + 16);
  svg.setAttribute("viewBox", `0 0 300 ${H}`);
  const max = Math.max(1, ...p.map((t) => Math.max(t.f, t.h)));
  const axe = 150, demi = 104, haut = 14;
  p.slice().reverse().forEach((t, i) => {
    const y = 8 + i * 18;
    const lf = (t.f / max) * demi, lh = (t.h / max) * demi;
    if (t.f) svg.append(el("rect", { x: axe - 22 - lf, y, width: lf, height: haut, rx: 3,
      fill: "var(--s5)" }));
    if (t.h) svg.append(el("rect", { x: axe + 22, y, width: lh, height: haut, rx: 3,
      fill: "var(--s1)" }));
    svg.append(el("text", { x: axe, y: y + 11, fill: "var(--texte-2)", "font-size": 10.5,
      "text-anchor": "middle" }, `${t.de}–${t.a}`));
    if (t.f) svg.append(el("text", { x: axe - 26 - lf, y: y + 11, fill: "var(--texte-3)",
      "font-size": 10, "text-anchor": "end" }, t.f));
    if (t.h) svg.append(el("text", { x: axe + 26 + lh, y: y + 11, fill: "var(--texte-3)",
      "font-size": 10 }, t.h));
  });

  // curseur de natalité
  const curseur = $("#d-natalite");
  const valeur = Math.round((e.politique.natalite ?? 0.5) * 100);
  if (document.activeElement !== curseur) curseur.value = valeur;
  const mots = valeur === 0 ? "aucun enfant voulu"
    : valeur < 30 ? "on attend d'être installés"
    : valeur < 70 ? "des enfants quand c'est possible"
    : "autant d'enfants que le lieu peut en porter";
  $("#d-natalite-libelle").textContent = `Désir d'enfants — ${mots}`;
  $("#d-natalite-note").textContent =
    "Les naissances dépendent aussi de la santé, des vivres, des places à l'abri " +
    "et de la charge des tout-petits.";
  curseur.oninput = () => {
    $("#d-natalite-libelle").textContent = `Désir d'enfants — ${curseur.value} %`;
  };
  curseur.onchange = () => api("/api/politique", { cle: "natalite", valeur: curseur.value / 100 });
}

function rendreJournal() {
  const entrees = [...S.etat.journal.entrees].reverse().slice(0, 120);
  $("#r-journal").innerHTML = entrees.map((e) =>
    `<div class="entree ${e.genre}"><span class="j">j ${e.jour}</span><span class="t">${e.texte}</span></div>`)
    .join("") || `<p class="vide">Rien à raconter pour l'instant.</p>`;
}

/* ---------------- infobulle ---------------- */
const bulle = () => $("#infobulle");
function infobulle(html, ev) {
  const b = bulle();
  b.innerHTML = html;
  b.style.visibility = "visible";
  const r = b.getBoundingClientRect();
  let x = ev.clientX + 14, y = ev.clientY + 14;
  if (x + r.width > innerWidth - 8) x = ev.clientX - r.width - 14;
  if (y + r.height > innerHeight - 8) y = ev.clientY - r.height - 14;
  b.style.left = `${x}px`; b.style.top = `${y}px`;
}
function cacherInfobulle() { bulle().style.visibility = "hidden"; }

/* ---------------- commandes ---------------- */
function arreterAuto() {
  if (auto) { clearInterval(auto); auto = null; }
  $("#b-auto").textContent = "▶ Laisser filer";
  $("#b-auto").classList.add("primaire");
}
$("#b-auto").onclick = () => {
  if (auto) return arreterAuto();
  $("#b-auto").textContent = "⏸ Suspendre";
  $("#b-auto").classList.remove("primaire");
  auto = setInterval(() => api("/api/avancer", { jours: 1 }), 550);
};
document.querySelectorAll("[data-jours]").forEach((b) => {
  b.onclick = () => api("/api/avancer", { jours: +b.dataset.jours });
});
$("#b-sauver").onclick = async () => {
  const nom = prompt("Nom de la sauvegarde", "partie");
  if (nom) await api("/api/sauver", { nom });
};
$("#b-recommencer").onclick = () => {
  if (!confirm("Repartir de zéro ? La partie en cours sera perdue si elle n'est pas sauvegardée.")) return;
  arreterAuto();
  S = null;
  $("#jeu").hidden = true;
  $("#accueil").hidden = false;
};
$("#b-theme").onclick = () => {
  const sombre = getComputedStyle(document.body).backgroundColor === "rgb(18, 18, 17)";
  document.documentElement.setAttribute("data-theme", sombre ? "light" : "dark");
};

/* --- accueil --- */
$("#a-commencer").onclick = () => api("/api/nouvelle", {
  nom: $("#a-nom").value, age: +$("#a-age").value, graine: +$("#a-graine").value,
  sexe: $("#a-sexe").value,
});
$("#a-charger").onclick = async () => {
  const nom = prompt("Nom de la sauvegarde à reprendre", "partie");
  if (nom) await api("/api/charger", { nom });
};

/* --- arrivées rapides --- */
document.querySelectorAll("[data-venir]").forEach((b) => {
  b.onclick = () => api("/api/personnes", { nombre: +b.dataset.venir });
});
$("#p-venir-n").onclick = () => {
  const n = prompt("Combien de personnes arrivent ? (1 à 50)", "20");
  if (n) api("/api/personnes", { nombre: Math.max(1, Math.min(50, +n || 1)) });
};

/* --- modale d'arrivée --- */
const modale = $("#modale-personne");
const COMPETENCES_UI = () => S.referentiel.competences;
function tirerAuSort() {
  const au = (liste) => liste[Math.floor(Math.random() * liste.length)];
  $("#n-sexe").value = Math.random() < 0.5 ? "f" : "h";
  const r = Math.random();
  $("#n-age").value = r < 0.58 ? 18 + Math.floor(Math.random() * 18)
    : r < 0.8 ? 36 + Math.floor(Math.random() * 15)
    : r < 0.92 ? 8 + Math.floor(Math.random() * 10)
    : 51 + Math.floor(Math.random() * 16);
  $("#n-specialite").value = au(COMPETENCES_UI());
  $("#n-nom").value = "";          // laissé vide : le serveur pioche dans le registre
  $("#n-histoire").value = "";
}
$("#n-tirer").onclick = tirerAuSort;
$("#p-ajouter").onclick = () => {
  const sel = $("#n-specialite");
  sel.innerHTML = S.referentiel.competences.map((c) => `<option value="${c}">${c}</option>`).join("");
  tirerAuSort();
  const cap = S.apercu.capacite_gouvernance, pop = S.etat.personnes.length;
  const vivres = S.apercu.autonomie_nourriture_jours;
  const avis = [];
  if (pop + 1 > cap) avis.push("au-delà de la capacité de coordination : tout le monde travaillera moins bien");
  if (S.apercu.abri < pop + 1) avis.push("pas assez d'abri pour une personne de plus");
  if (vivres < 15) avis.push(`seulement ${nb(vivres, 1)} jours de vivres d'avance`);
  $("#n-avertissement").textContent = avis.length ? `⚠ ${avis.join(" ; ")}.` : "";
  modale.showModal();
};
modale.addEventListener("close", () => {
  if (modale.returnValue !== "ok") return;
  api("/api/personne", {
    nom: $("#n-nom").value,
    age: +$("#n-age").value,
    specialite: $("#n-specialite").value,
    sexe: $("#n-sexe").value,
    histoire: $("#n-histoire").value,
  });
});

addEventListener("keydown", (e) => {
  if (e.target.matches("input, select, textarea")) return;
  if (e.key === " ") { e.preventDefault(); $("#b-auto").click(); }
  if (e.key === "ArrowRight") api("/api/avancer", { jours: e.shiftKey ? 7 : 1 });
});

/* --- démarrage : reprendre la partie en cours s'il y en a une --- */
fetch("/api/etat").then((r) => r.json()).then((d) => {
  if (d && d.etat) { S = d; rendre(); }
});
