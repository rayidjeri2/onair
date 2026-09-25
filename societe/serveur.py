"""Petit serveur HTTP (bibliothèque standard) : API JSON + interface web."""

from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import moteur
from .catalogue import disponibles
from .modele import COMPETENCES, RESSOURCES, TACHES, TYPES_PARCELLE, Etat

WEB = Path(__file__).parent / "web"
SAUVEGARDES = Path("sauvegardes")


class Partie:
    """L'état courant, protégé par un verrou (le serveur est multithread)."""

    def __init__(self) -> None:
        self.verrou = threading.Lock()
        self.etat: Etat | None = None

    def exige(self) -> Etat:
        if self.etat is None:
            raise ValueError("aucune partie en cours")
        return self.etat


PARTIE = Partie()


def instantane(etat: Etat) -> dict[str, Any]:
    return {
        "etat": etat.vers_dict(),
        "apercu": moteur.apercu(etat),
        "chantiers": disponibles(etat),
        "referentiel": {
            "taches": TACHES,
            "competences": COMPETENCES,
            "ressources": RESSOURCES,
            "types_parcelle": TYPES_PARCELLE,
        },
    }


def traiter(chemin: str, corps: dict[str, Any]) -> dict[str, Any]:
    """Routage de l'API. Retourne toujours un instantané complet de la partie."""
    with PARTIE.verrou:
        if chemin == "/api/nouvelle":
            PARTIE.etat = moteur.creer_societe(
                nom_fondateur=corps.get("nom", "Ana"),
                age=int(corps.get("age", 30)),
                graine=int(corps.get("graine", 1)),
                sexe=str(corps.get("sexe", "f")),
            )
            return instantane(PARTIE.etat)

        if chemin == "/api/etat":
            if PARTIE.etat is None:
                return {"etat": None}
            return instantane(PARTIE.etat)

        etat = PARTIE.exige()

        if chemin == "/api/avancer":
            moteur.avancer(etat, int(corps.get("jours", 1)))
        elif chemin == "/api/personne":
            moteur.ajouter_personne(
                etat,
                nom=str(corps.get("nom", "")),
                age=int(corps.get("age", 28)),
                specialite=str(corps.get("specialite", "agriculture")),
                histoire=str(corps.get("histoire", "")),
                sexe=str(corps.get("sexe", "f")),
            )
        elif chemin == "/api/affectation":
            moteur.affecter(etat, int(corps["id"]), str(corps["tache"]))
        elif chemin == "/api/affectations":
            # affectation groupée : on ignore silencieusement ceux qui ne peuvent pas
            # prendre la tâche (les enfants), au lieu de rejeter tout le lot
            for id_personne, tache in corps.get("affectations", {}).items():
                try:
                    moteur.affecter(etat, int(id_personne), str(tache))
                except ValueError:
                    continue
        elif chemin == "/api/politique":
            moteur.regler_politique(etat, str(corps["cle"]), float(corps["valeur"]))
        elif chemin == "/api/chantier":
            moteur.lancer_chantier(etat, str(corps["cle"]))
        elif chemin == "/api/annuler-chantier":
            moteur.annuler_chantier(etat)
        elif chemin == "/api/sauver":
            nom = str(corps.get("nom", "partie"))
            SAUVEGARDES.mkdir(exist_ok=True)
            fichier = SAUVEGARDES / f"{_assainir(nom)}.json"
            fichier.write_text(json.dumps(etat.vers_dict(), ensure_ascii=False), encoding="utf-8")
            etat.journal.noter(etat.jour, f"Partie sauvegardée ({fichier.name}).", "info")
        elif chemin == "/api/charger":
            nom = _assainir(str(corps.get("nom", "partie")))
            fichier = SAUVEGARDES / f"{nom}.json"
            if not fichier.exists():
                raise ValueError("sauvegarde introuvable")
            PARTIE.etat = Etat.depuis_dict(json.loads(fichier.read_text(encoding="utf-8")))
            return instantane(PARTIE.etat)
        else:
            raise ValueError(f"route inconnue : {chemin}")

        return instantane(etat)


def _assainir(nom: str) -> str:
    garde = [c for c in nom.strip().lower() if c.isalnum() or c in "-_"]
    return "".join(garde)[:40] or "partie"


class Gestionnaire(BaseHTTPRequestHandler):
    server_version = "SimSociete/1.0"

    def log_message(self, format: str, *args: Any) -> None:  # silence
        pass

    def _repondre(self, code: int, contenu: bytes, type_mime: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", type_mime)
        self.send_header("Content-Length", str(len(contenu)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(contenu)

    def _json(self, code: int, charge: dict[str, Any]) -> None:
        self._repondre(code, json.dumps(charge, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        chemin = self.path.split("?")[0]
        if chemin.startswith("/api/"):
            try:
                self._json(200, traiter(chemin, {}))
            except Exception as erreur:  # noqa: BLE001
                self._json(400, {"erreur": str(erreur)})
            return
        nom = "index.html" if chemin in ("/", "") else chemin.lstrip("/")
        fichier = (WEB / nom).resolve()
        if not str(fichier).startswith(str(WEB.resolve())) or not fichier.is_file():
            self._repondre(404, b"introuvable", "text/plain; charset=utf-8")
            return
        type_mime = mimetypes.guess_type(fichier.name)[0] or "application/octet-stream"
        if type_mime.startswith("text/") or type_mime.endswith("javascript"):
            type_mime += "; charset=utf-8"
        self._repondre(200, fichier.read_bytes(), type_mime)

    def do_POST(self) -> None:  # noqa: N802
        longueur = int(self.headers.get("Content-Length", 0))
        brut = self.rfile.read(longueur) if longueur else b"{}"
        try:
            corps = json.loads(brut or b"{}")
            self._json(200, traiter(self.path.split("?")[0], corps))
        except Exception as erreur:  # noqa: BLE001
            self._json(400, {"erreur": str(erreur)})


def servir(hote: str = "127.0.0.1", port: int = 8000) -> None:
    serveur = ThreadingHTTPServer((hote, port), Gestionnaire)
    print(f"Simulation de société : http://{hote}:{port}")
    print("Ctrl+C pour arrêter.")
    try:
        serveur.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
    finally:
        serveur.server_close()
