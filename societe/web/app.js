/* Interface de la simulation de société. Tout l'état vient du serveur ;
   la page ne fait que l'afficher et renvoyer les décisions du joueur. */

let S = null;             // dernier instantané reçu
let filtre = "tout";
let seulementRealisables = true;
let auto = null;          // battement de l'horloge
let vitesse = 1;          // jours par battement (0 = suspendu)
let filtreAction = "population";

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
  rendreSavoirs();
  rendreActions();
  rendreCatalogue();
  rendreRessources();
  rendreCommerce();
  rendreDemographie();
  rendreGraphiques();
  rendreJournal();
  if (S.etat.termine) arreterAuto();
}

function rendreBarre() {
  const e = S.etat, d = e.derive, a = S.apercu;
  $("#b-date").textContent = d.date;
  $("#b-saison").dataset.saison = d.saison;
  $("#b-saison").title = d.saison;
  $("#b-meteo").textContent = `${e.meteo.description}, ${nb(e.meteo.temperature, 1)} °C` +
    (e.meteo.pluie > 0 ? ` · ${nb(e.meteo.pluie, 1)} mm` : "");

  // tendance sur les trente derniers jours relevés
  const h = e.historique;
  const avant = h.length > 30 ? h[h.length - 31] : h[0];
  const tendance = (cle, actuel) => {
    if (!avant || avant[cle] == null) return "";
    const delta = actuel - avant[cle];
    const seuil = Math.max(0.5, Math.abs(avant[cle]) * 0.03);
    if (delta > seuil) return `<span class="tendance monte" title="en hausse">▲</span>`;
    if (delta < -seuil) return `<span class="tendance baisse" title="en baisse">▼</span>`;
    return "";
  };

  const etat = (v, bas, tresbas) => v <= tresbas ? "alerte" : (v <= bas ? "prudence" : "bon");
  const eauCritique = a.eau_deficit > 0;

  const cellules = [
    {
      cle: "Habitants", valeur: nb(d.population), unite: "",
      part: null, etat: "bon", fleche: tendance("population", d.population),
      aide: `${d.actifs} en âge de travailler, ${d.enfants} enfant${d.enfants > 1 ? "s" : ""}, ` +
            `${d.anciens} ancien${d.anciens > 1 ? "s" : ""}.` +
            (d.grossesses ? `<br>${d.grossesses} grossesse${d.grossesses > 1 ? "s" : ""} en cours.` : ""),
    },
    {
      cle: "Vivres", valeur: nb(a.autonomie_nourriture_jours, 1), unite: "j",
      part: Math.min(1, a.autonomie_nourriture_jours / 60),
      etat: etat(a.autonomie_nourriture_jours, 12, 4),
      fleche: tendance("nourriture", e.stocks.nourriture),
      aide: `${nb(e.stocks.nourriture)} portions en réserve sur ${nb(a.grenier)} stockables.` +
            `<br>Il en faut ${nb(a.autonomie_nourriture_jours ? e.stocks.nourriture / a.autonomie_nourriture_jours : 0, 1)} par jour.` +
            `<br><i>L'hiver dure 90 jours à rendement réduit.</i>`,
    },
    {
      cle: "Eau", valeur: nb(Math.max(0, a.autonomie_eau_jours), 1),
      unite: eauCritique ? "j ⚠" : "j",
      part: Math.min(1, Math.max(0, a.autonomie_eau_jours) / 10),
      etat: eauCritique ? (a.autonomie_eau_jours < 2 ? "alerte" : "prudence")
        : etat(a.autonomie_eau_jours, 4, 1),
      fleche: tendance("eau", e.stocks.eau),
      aide: `Il arrive ${nb(a.eau_apport_jour)} L par jour, il en faut ${nb(a.eau_besoin_jour)}.` +
            (eauCritique ? `<br><b>Il manque ${nb(Math.abs(a.eau_deficit))} L chaque jour</b> : porter l'eau, ` +
              `capter la source ou creuser un puits.` : "") +
            `<br>${nb(e.stocks.eau)} L stockés sur ${nb(a.eau_max)}.`,
    },
    {
      cle: "Abri", valeur: `${nb(a.abri)}/${nb(d.population)}`, unite: "",
      part: d.population ? Math.min(1, a.abri / d.population) : 1,
      etat: a.abri >= d.population ? "bon" : (a.abri >= d.population * 0.7 ? "prudence" : "alerte"),
      fleche: "",
      aide: a.abri >= d.population
        ? "Tout le monde dort au sec."
        : `${nb(d.population - a.abri)} personne(s) sans place : santé, moral et énergie en souffrent.`,
    },
    {
      cle: "Moral", valeur: nb(d.moral), unite: "", part: d.moral / 100,
      etat: etat(d.moral, 40, 22), fleche: tendance("moral", d.moral),
      aide: "Dépend du confort, des vivres, de l'abri, de la cohésion et de la famille." +
            "<br>En dessous de 6, les adultes finissent par partir.",
    },
    {
      cle: "Santé", valeur: nb(d.sante), unite: "", part: d.sante / 100,
      etat: etat(d.sante, 60, 35), fleche: tendance("sante", d.sante),
      aide: "Dépend des rations, de l'eau, de la salubrité, du froid et des soins." +
            "<br>À zéro, on meurt d'épuisement.",
    },
    {
      cle: "Cohésion", valeur: nb(e.cohesion * 100), unite: "%", part: e.cohesion,
      etat: etat(e.cohesion * 100, 55, 35), fleche: tendance("cohesion", e.cohesion),
      aide: "Se dégrade quand le groupe dépasse ce que la gouvernance peut tenir." +
            "<br>La salle commune, le conseil et l'école la soutiennent.",
    },
    {
      cle: "Coordin.", valeur: nb(a.coordination * 100), unite: "%", part: a.coordination,
      etat: etat(a.coordination * 100, 75, 55), fleche: "",
      aide: `Part du travail réellement utile. Gouvernance : ${e.gouvernance}, ` +
            `tenable jusqu'à ${nb(a.capacite_gouvernance)} personnes.` +
            (d.population > a.capacite_gouvernance
              ? `<br><b>${nb(d.population - a.capacite_gouvernance)} de trop</b> : chacun travaille moins bien.`
              : ""),
    },
  ];

  $("#b-indicateurs").innerHTML = cellules.map((c, i) => `
    <div class="ind" data-etat="${c.etat}" data-i="${i}">
      <div class="et">${c.cle}</div>
      <div class="va">${c.valeur}${c.unite ? `<span class="unite">${c.unite}</span>` : ""}${c.fleche}</div>
      ${c.part == null ? "" :
        `<div class="mini"><i style="width:${Math.max(2, Math.min(100, c.part * 100))}%"></i></div>`}
    </div>`).join("");

  $("#b-indicateurs").querySelectorAll(".ind").forEach((n) => {
    const c = cellules[+n.dataset.i];
    n.addEventListener("pointermove", (ev) => infobulle(`<b>${c.cle}</b><br>${c.aide}`, ev));
    n.addEventListener("pointerleave", cacherInfobulle);
  });
}

function choixMetier(p, enfant) {
  const info = S.apercu.metiers || { possibles: [], places: 0, exerces: 0 };
  if (enfant || !info.possibles.length) return "";
  const libre = info.exerces < info.places || p.metier;
  const options = [`<option value="">sans métier</option>`].concat(
    info.possibles.map((m) =>
      `<option value="${m.cle}" ${p.metier === m.cle ? "selected" : ""}>` +
      `${m.nom} ×${m.bonus}</option>`)).join("");
  return `<div class="metier-choix"><select data-metier="${p.id}" ${libre ? "" : "disabled"}>` +
    `${options}</select></div>`;
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
    const rend = (S.apercu.rendements || {})[p.id];
    const meilleur = rend ? Math.max(...Object.values(rend)) : 0;
    const options = Object.entries(taches).map(([k, v]) => {
      const part = rend && rend[k] ? Math.round((rend[k] / meilleur) * 100) : null;
      // le rendement d'abord : il reste lisible même si le libellé est tronqué
      return `<option value="${k}" ${p.tache === k ? "selected" : ""}>` +
        `${part !== null ? `${String(part).padStart(3, " ")} % · ` : ""}${v}</option>`;
    }).join("");
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
    if (p.metier) {
      const m = (S.apercu.metiers.possibles || []).find((x) => x.cle === p.metier);
      etiquettes.push(`<span class="etiq metier" title="${m ? m.description : ""}">` +
        `${m ? m.nom : p.metier}</span>`);
    }
    if (!enfant && p.polyvalence >= 0.6) etiquettes.push(
      `<span class="etiq polyvalent" title="se débrouille dans presque tous les travaux">polyvalent${p.sexe === "f" ? "e" : ""}</span>`);
    else if (!enfant && p.polyvalence <= 0.22) etiquettes.push(
      `<span class="etiq specialise" title="peu efficace hors de sa spécialité">spécialisé${p.sexe === "f" ? "e" : ""}</span>`);
    const risque = (S.apercu.risques || {})[p.id];
    return `<div class="personne">
      <div class="tete"><span class="nom">${p.nom}</span>
        <span class="meta" title="risque de décès dans l'année : ${risque ?? "?"} %">${p.age} ans ·
          ${enfant ? p.classe_age || "enfant" : `${spec[0]} ${Math.round(spec[1] * 100)} %`}</span></div>
      <div class="jauges">${jauge("énergie", p.energie)}${jauge("santé", p.sante)}${jauge("moral", p.moral)}</div>
      ${etiquettes.length ? `<div class="famille">${etiquettes.join("")}</div>` : ""}
      <select data-personne="${p.id}" ${enfant ? "disabled" : ""}>${options}</select>
      ${choixMetier(p, enfant)}
      ${p.tache === "construction" && !e.chantiers.length && !e.intendance
        ? `<div class="avert">aucun chantier ouvert : cette journée est perdue</div>` : ""}
      ${p.histoire ? `<div class="histoire">« ${p.histoire} »</div>` : ""}
    </div>`;
  }).join("") || `<p class="vide">Plus personne ici.</p>`;

  $("#p-liste").querySelectorAll("select[data-personne]").forEach((s) => {
    s.onchange = () => api("/api/affectation", { id: +s.dataset.personne, tache: s.value });
  });
  $("#p-liste").querySelectorAll("select[data-metier]").forEach((s) => {
    s.onchange = () => api("/api/metier", { id: +s.dataset.metier, metier: s.value });
  });

  rendreIntendance();
  rendreRedeploiement();
  const cap = S.apercu.capacite_gouvernance;
  const places = S.apercu.abri - e.personnes.length;
  const notes = [];
  notes.push(e.personnes.length > cap
    ? `Au-delà de ${cap} personnes, la coordination se perd : il faut des lieux et des règles communes.`
    : `Coordination tenable jusqu'à ${cap} personnes (${e.gouvernance}).`);
  notes.push(places > 0 ? `${places} place${places > 1 ? "s" : ""} libre${places > 1 ? "s" : ""} à l'abri.`
    : `Plus une place à l'abri : chaque arrivée dégrade la santé et le moral.`);
  notes.push(`${nb(S.apercu.autonomie_nourriture_jours, 1)} jours de vivres d'avance.`);
  const m = S.apercu.metiers;
  if (m && m.places) notes.push(`${m.exerces}/${m.places} métier(s) à plein temps.`);
  $("#p-note").textContent = notes.join(" ");
}

function rendreIntendance() {
  const actif = S.etat.intendance;
  const bloc = $("#i-bloc");
  bloc.classList.toggle("active", actif);
  $("#i-etat").textContent = actif
    ? "elle décide chaque matin"
    : "vous décidez de tout";
  $("#i-bascule").textContent = actif ? "Reprendre" : "Confier";
  $("#i-bascule").classList.toggle("primaire", !actif);
  $("#i-bascule").classList.toggle("discret", actif);

  const info = S.apercu.intendance || {};
  if (actif) {
    const manque = Object.entries(info.manquants || {})
      .map(([r, q]) => `${nb(q, 1)} ${r}`).join(", ");
    const suite = manque ? `rassemble ${manque}`
      : S.etat.chantier ? "chantier en cours"
      : "ouvre le chantier demain matin";
    $("#i-explication").textContent = info.cible_nom
      ? `Vise « ${info.cible_nom} » — ${suite}. ` +
        "Vos changements d'affectation tiennent jusqu'au lendemain matin."
      : "Rien à entreprendre pour l'instant : tout le monde produit.";
  } else {
    $("#i-explication").textContent =
      "Elle choisit le chantier et affecte chacun selon ses aptitudes, " +
      "en donnant la priorité à l'eau, aux vivres, puis à l'abri.";
  }
  $("#i-bascule").onclick = () => api("/api/intendance", { actif: !actif });
}

function rendreRedeploiement() {
  const taches = S.referentiel.taches;
  const select = $("#p-cible");
  const garde = select.value;
  select.innerHTML = Object.entries(taches)
    .filter(([k]) => k !== "repos")
    .map(([k, v]) => `<option value="${k}">${v}</option>`).join("");
  select.value = garde && taches[garde] ? garde : "nourriture";

  const rend = S.apercu.rendements || {};
  const adultes = S.etat.personnes.filter((p) => rend[p.id]);
  const classes = (tache) => adultes.slice()
    .sort((x, y) => (rend[y.id][tache] || 0) - (rend[x.id][tache] || 0));

  const decrire = () => {
    const t = select.value;
    const ordre = classes(t);
    $("#p-redeploiement-note").textContent = ordre.length
      ? `Les plus efficaces : ${ordre.slice(0, 3).map((p) => p.nom).join(", ")}.`
      : "Personne en âge de travailler.";
  };
  select.onchange = decrire;
  decrire();

  document.querySelectorAll("[data-redeploie]").forEach((b) => {
    b.onclick = () => {
      const t = select.value;
      const combien = b.dataset.redeploie === "tous" ? adultes.length : +b.dataset.redeploie;
      const choisis = classes(t).slice(0, combien);
      if (!choisis.length) return;
      const affectations = {};
      for (const p of choisis) affectations[p.id] = t;
      api("/api/affectations", { affectations });
    };
  });
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
  const liste = S.etat.chantiers || [];
  const bloc = $("#c-chantier");
  $("#c-compte").textContent = `${liste.length}/${S.apercu.chantiers_max ?? 1}`;
  if (!liste.length) {
    bloc.innerHTML = `<p class="vide">Aucun chantier en cours. Les personnes affectées à
      « travailler sur le chantier » ne produisent rien tant que vous n'en ouvrez pas un.</p>`;
    return;
  }
  bloc.innerHTML = liste.map((c) => {
    const part = c.travail_fait / c.travail_requis;
    const reste = Math.max(0, c.travail_requis - c.travail_fait);
    return `<div class="chantier-ligne">
      <div class="tete"><span class="nom">${c.nom}</span>
        <span class="reste">${nb(c.travail_fait, 1)} / ${nb(c.travail_requis)} j-h</span></div>
      <div class="barre-progres"><i style="width:${Math.min(100, part * 100)}%"></i></div>
      <div class="tete"><span class="reste">il reste ${nb(reste, 1)} jours-homme</span>
        <button class="discret" data-annuler="${c.cle}">abandonner</button></div>
    </div>`;
  }).join("") +
  (liste.length > 1
    ? `<p class="note">Les bras se répartissent à parts égales entre les chantiers ouverts.</p>`
    : "");
  bloc.querySelectorAll("[data-annuler]").forEach((b) => {
    b.onclick = () => api("/api/annuler-chantier", { cle: b.dataset.annuler });
  });
}

function rendreSavoirs() {
  const info = S.apercu.savoirs;
  if (!info) return;
  const ages = info.ages || {};
  $("#s-resume").textContent =
    `${info.acquis.length} découverte(s) acquise(s). ` +
    (info.memoire
      ? "L'écriture et les archives les mettent à l'abri de l'oubli."
      : "Sans écriture ni archives, un savoir que plus personne ne pratique se perd.");

  $("#s-encours").innerHTML = info.en_cours.slice(0, 4).map((s) => `
    <div class="savoir">
      <div class="tete"><span class="nom">
        <span class="age-savoir">${ages[s.age] || s.age}</span>${s.nom}</span>
        <span class="part">${Math.round(s.part * 100)} %</span></div>
      <div class="desc">${s.description}</div>
      <div class="piste"><i style="width:${Math.max(1, s.part * 100)}%;background:var(--s5)"></i></div>
    </div>`).join("") || `<p class="vide">Rien ne progresse : il faut pratiquer, ou chercher.</p>`;

  $("#s-acquis").innerHTML = info.acquis.map((s) =>
    `<span class="chip acquis" title="${s.description}">${s.nom}</span>`).join("");
  $("#s-avenir").innerHTML = info.a_venir.map((s) =>
    `<span class="chip ferme" title="exige : ${s.exige.join(", ")}">${s.nom}</span>`).join("")
    || `<span class="chip">plus rien : tout est à portée</span>`;
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

const GROUPES_RESSOURCES = [
  {
    titre: "Subsistance", couleur: "var(--s3)",
    ressources: {
      nourriture: {
        libelle: "Nourriture",
        role: "cultures et cueillette",
        aide: "Une portion par personne et par jour, moins pour les enfants. " +
              "Ce qui dépasse la capacité de conservation est perdu : caves et hangars l'augmentent.",
      },
      eau: {
        libelle: "Eau",
        role: "source, puits, pluie",
        aide: "50 litres par adulte et par jour. Le débit compte plus que le stock : " +
              "un puits ajoute 320 litres par jour, la source 300.",
      },
    },
  },
  {
    titre: "Matériaux bruts", couleur: "var(--s2)",
    ressources: {
      bois: { libelle: "Bois", role: "bûcheronnage en forêt",
        aide: "Chauffe l'hiver et alimente l'atelier, qui le transforme en planches." },
      pierre: { libelle: "Pierre", role: "extraction",
        aide: "Fondations, four, forge, réservoirs, chemin." },
      terre: { libelle: "Terre", role: "avec la pierre",
        aide: "Murs en terre crue, poêles de masse, retenue d'eau." },
      recup: { libelle: "Récupération", role: "chemin, recyclerie",
        aide: "Métal, plastique, verre ramassés ou refondus. " +
              "C'est la matière première de l'énergie solaire et de l'éolienne." },
    },
  },
  {
    titre: "Transformé", couleur: "var(--s1)",
    ressources: {
      planches: { libelle: "Planches", role: "atelier, scierie",
        aide: "Un stère donne trois mètres carrés de planches, deux fois plus avec la scierie." },
      outils: { libelle: "Outils", role: "atelier, forge",
        aide: "Accélèrent tous les chantiers, jusqu'à 30 % de mieux." },
      compost: { libelle: "Compost", role: "toilettes sèches",
        aide: "Ferme le cycle des nutriments et remonte le rendement des cultures." },
      electricite: { libelle: "Électricité", role: "solaire, éolienne",
        aide: "Se perd si elle n'est pas stockée : les batteries fixent la capacité." },
    },
  },
];

function rendreRessources() {
  const e = S.etat, u = S.referentiel.ressources, a = S.apercu;
  const caps = a.capacites || {};
  const flux = a.flux || {};
  const morceaux = [];
  const aides = [];

  for (const groupe of GROUPES_RESSOURCES) {
    morceaux.push(`<div class="groupe-res">
      <span class="pastille-res" style="background:${groupe.couleur}"></span>${groupe.titre}</div>`);
    for (const [cle, info] of Object.entries(groupe.ressources)) {
      const v = e.stocks[cle] ?? 0;
      const cap = caps[cle] || 0;
      const part = cap ? Math.min(1, v / cap) : null;
      const f = flux[cle] ?? 0;
      // une ressource qu'on n'a pas encore les moyens de produire reste discrète
      const inactive = v <= 0 && !cap && Math.abs(f) < 0.05;
      const classe = inactive ? "inactif"
        : v <= 0 ? "epuise" : (part !== null && part >= 0.98 ? "pleine" : "");
      const signe = f > 0.05 ? "monte" : (f < -0.05 ? "baisse" : "");
      const fluxTexte = Math.abs(f) < 0.05 ? "—"
        : `${f > 0 ? "+" : "−"}${nb(Math.abs(f), Math.abs(f) < 10 ? 1 : 0)}/j`;
      aides.push({ cle, info, v, cap, f, unite: u[cle] });
      morceaux.push(`<div class="ressource ${classe}" data-res="${cle}">
        <span class="nom">${info.libelle}<small>${info.role}</small></span>
        <span class="q">${nb(v, v < 10 && v > 0 ? 1 : 0)}<span class="u">${u[cle]}</span></span>
        <span class="flux ${signe}">${fluxTexte}</span>
        ${part === null ? "" :
          `<span class="cap"><i class="${part < 0.8 && part > 0.05 ? "bon" : ""}"
            style="width:${Math.max(2, part * 100)}%"></i></span>`}
      </div>`);
    }
  }
  $("#r-liste").innerHTML = morceaux.join("");

  $("#r-liste").querySelectorAll(".ressource").forEach((n) => {
    const d = aides.find((x) => x.cle === n.dataset.res);
    n.addEventListener("pointermove", (ev) => {
      const lignes = [`<b>${d.info.libelle}</b>`, d.info.aide];
      if (d.cap) lignes.push(`Capacité : ${nb(d.v)} / ${nb(d.cap)} ${d.unite}.`);
      if (Math.abs(d.f) >= 0.05) {
        lignes.push(d.f > 0
          ? `Gagne ${nb(d.f, 1)} ${d.unite} par jour au rythme actuel.`
          : `Perd ${nb(-d.f, 1)} ${d.unite} par jour : tiendra ${nb(d.v / -d.f, 1)} jours.`);
      }
      infobulle(lignes.join("<br>"), ev);
    });
    n.addEventListener("pointerleave", cacherInfobulle);
  });

  // ce que l'outillage et les savoirs ont changé
  const prod = S.apercu.productivite || {};
  const gains = Object.entries(prod).filter(([, v]) => v > 1.01)
    .map(([nom, v]) => `${nom} ×${nb(v, 2)}`);
  const ligne = document.getElementById("r-productivite");
  if (ligne) {
    ligne.textContent = gains.length
      ? `Productivité gagnée : ${gains.join(", ")}.`
      : "";
  }

  // ce qui bloque le prochain chantier
  const bloques = S.chantiers.filter((c) => !c.bloque && Object.keys(c.manquants).length);
  const manques = {};
  for (const c of bloques) {
    for (const [r, q] of Object.entries(c.manquants)) {
      manques[r] = Math.min(manques[r] ?? Infinity, q);
    }
  }
  const liste = Object.entries(manques).sort((a, b) => a[1] - b[1]).slice(0, 3);
  $("#r-manquants").textContent = liste.length
    ? `Il manque ${liste.map(([r, q]) => `${nb(q, 1)} ${r}`).join(", ")} pour ouvrir d'autres chantiers.`
    : "";
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
    { titre: "Trésor commun", series: [
      ["pièces", "var(--s4)", ech.map((p) => p.tresor ?? 0)]] },
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

function rendreCommerce() {
  const m = S.apercu.marche;
  if (!m) return;
  $("#m-etat").textContent = !m.route_ouverte
    ? "Personne ne vient jusqu'ici : il faut un chemin d'accès, ou la roue."
    : !m.commerce_actif
      ? "La route est fermée : le lieu vit en autarcie."
      : `Prochaine caravane dans ${m.prochaine_caravane} jour(s). ` +
        `Impôt ${Math.round(m.impot * 100)} %, réserve gardée ${Math.round(m.reserve_jours)} jours.`;

  const tuiles = [
    ["Trésor commun", `${nb(m.tresor)} ₽`],
    ["Fortunes privées", `${nb(m.avoir_total)} ₽`],
    ["Par personne", `${nb(m.avoir_moyen)} ₽`],
    ["Inégalité", m.inegalite.toFixed(2).replace(".", ",")],
  ];
  $("#m-tuiles").innerHTML = tuiles.map(([t, v]) =>
    `<div class="demo-tuile"><div class="et">${t}</div><div class="va">${v}</div></div>`).join("");

  const d = m.dernier || {};
  const lignes = (titre, offres, classe) => !offres || !offres.length ? "" :
    `<div class="titre-echange">${titre}</div>` + offres.map((o) =>
      `<div class="echange ${classe}"><span>${o.ressource} · ${nb(o.quantite, 1)} à ${nb(o.prix, 2)} ₽</span>
       <span class="q">${classe === "vente" ? "+" : "−"}${nb(o.valeur)} ₽</span></div>`).join("");
  $("#m-echanges").innerHTML = d.jour === undefined
    ? `<p class="vide">Aucune caravane n'est encore passée.</p>`
    : `<p class="note">Dernier passage au jour ${d.jour}.</p>` +
      lignes("Vendu", d.ventes, "vente") + lignes("Acheté", d.achats, "achat") ||
      `<p class="vide">La dernière caravane est repartie les mains vides.</p>`;

  $("#m-prix").innerHTML = Object.entries(m.prix).map(([r, p]) =>
    `<span>${r}</span><span>${nb(p, 2)} ₽</span>`).join("") +
    (Object.keys(m.surplus).length
      ? `<span style="color:var(--bon)">à vendre</span><span style="color:var(--bon)">${
          Object.entries(m.surplus).map(([r, q]) => `${nb(q)} ${r}`).join(", ")}</span>` : "") +
    (Object.keys(m.manques).length
      ? `<span style="color:var(--s2)">à acheter</span><span style="color:var(--s2)">${
          Object.entries(m.manques).map(([r, q]) => `${nb(q, 1)} ${r}`).join(", ")}</span>` : "");
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

/* ---------------- horloge ---------------- */
function battre() {
  if (auto) clearInterval(auto);
  auto = null;
  if (vitesse > 0) auto = setInterval(() => api("/api/avancer", { jours: vitesse }), 620);
  document.querySelectorAll("[data-vitesse]").forEach((b) => {
    b.classList.toggle("vitesse-active", +b.dataset.vitesse === vitesse);
  });
}
function arreterAuto() { vitesse = 0; battre(); }
document.querySelectorAll("[data-vitesse]").forEach((b) => {
  b.onclick = () => { vitesse = +b.dataset.vitesse; battre(); };
});
$("#b-pas").onclick = () => api("/api/avancer", { jours: 1 });

/* ---------------- interventions ---------------- */
let signatureActions = null;

function rendreActions() {
  const actions = S.actions || [];
  // le panneau ne se redessine que si nécessaire : sinon l'horloge effacerait
  // les valeurs en cours de saisie à chaque battement
  const signature = `${filtreAction}|${actions.length}|${JSON.stringify(S.reglages || {})}`;
  if (signature === signatureActions && $("#x-liste").children.length) return;
  signatureActions = signature;
  const cats = [...new Map(actions.map((a) => [a.categorie, a.categorie_nom])).entries()];
  $("#x-filtres").innerHTML = cats.map(([c, nom]) =>
    `<button data-cat-action="${c}" aria-pressed="${filtreAction === c}">${nom}</button>`).join("");
  $("#x-filtres").querySelectorAll("button").forEach((b) => {
    b.onclick = () => { filtreAction = b.dataset.catAction; rendreActions(); };
  });

  const reglages = S.reglages || {};
  const champ = (a, p) => {
    const id = `x-${a.cle}-${p.cle}`;
    const courant = reglages[`${a.cle}.${p.cle}`];
    const valeur = courant !== undefined ? courant : p.defaut;
    if (p.type === "choix") {
      return `<div class="param large"><label for="${id}">${p.libelle}</label>
        <select id="${id}">${p.options.map((o) =>
          `<option value="${o}" ${o === valeur ? "selected" : ""}>${o}</option>`).join("")}</select></div>`;
    }
    return `<div class="param"><label for="${id}">${p.libelle}${p.unite ? ` (${p.unite})` : ""}</label>
      <input id="${id}" type="number" value="${valeur}" min="${p.min}" max="${p.max}" step="${p.pas}"></div>`;
  };

  const liste = actions.filter((a) => a.categorie === filtreAction);
  $("#x-liste").innerHTML = liste.map((a) => `
    <div class="action" data-action="${a.cle}">
      <h3>${a.nom}</h3>
      ${a.durable ? `<span class="marque-durable">réglage durable</span>` : ""}
      <div class="desc">${a.description}</div>
      <div class="params">${a.parametres.map((p) => champ(a, p)).join("")}</div>
      <button data-appliquer="${a.cle}">Appliquer</button>
    </div>`).join("");

  $("#x-liste").querySelectorAll("[data-appliquer]").forEach((b) => {
    b.onclick = () => {
      const cle = b.dataset.appliquer;
      const a = actions.find((x) => x.cle === cle);
      const parametres = {};
      for (const p of a.parametres) {
        const n = document.getElementById(`x-${cle}-${p.cle}`);
        parametres[p.cle] = p.type === "choix" ? n.value : +n.value;
      }
      api("/api/action", { cle, parametres });
    };
  });
}

/* ---------------- commandes ---------------- */
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
$("#a-commencer").onclick = async () => {
  await api("/api/nouvelle", {
    nom: $("#a-nom").value, age: +$("#a-age").value, graine: +$("#a-graine").value,
    sexe: $("#a-sexe").value,
  });
  await api("/api/intendance", { actif: true });   // le quotidien se gère tout seul
  vitesse = 1; battre();                            // et le temps se met à tourner
};
$("#a-degraine").onclick = () => {
  $("#a-graine").value = Math.floor(Math.random() * 99999) + 1;
};
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
  if (e.key === " ") { e.preventDefault(); vitesse = vitesse > 0 ? 0 : 1; battre(); }
  if (e.key === "ArrowRight") api("/api/avancer", { jours: e.shiftKey ? 7 : 1 });
});

/* --- démarrage : reprendre la partie en cours s'il y en a une --- */
fetch("/api/etat").then((r) => r.json()).then((d) => {
  if (d && d.etat) { S = d; rendre(); battre(); }
});
