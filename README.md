# HA-Lethe

Home-Assistant-Integration für den **Lethe Messenger**. Home Assistant schreibt dir als eigener Bot in Lethe – für Alarme, Statusmeldungen oder Infos.

## Was ist Lethe?

[Lethe](https://letheapp.de) ist ein datenschutzorientierter Messenger mit Ende-zu-Ende-Verschlüsselung. Nachrichten liegen auf dem Server nur als Chiffretext, die Schlüssel werden auf dem Gerät erzeugt.

- Verschlüsselte Einzel- und Gruppenchats
- Sprach- und Videoanrufe (WebRTC)
- Statusmeldungen und Umfragen
- Mehrere Geräte pro Konto, gekoppelt per QR-Code („Verknüpfte Geräte“)
- Standortfreigabe auf Basis von OpenStreetMap
- Optionaler eingebauter Tor-Client
- FOSS-Build ohne Google-Dienste: Push über einen eigenen WebSocket-Dienst statt Firebase

Die Android-App ist Open Source ([Lethe-Community](https://github.com/thestealth131205/Lethe-Community), GPL-3.0). Für die Nutzung brauchst du ein Lethe-Konto.

Lethe hat außerdem eine **Bot-API**. Über sie kann ein Dienst als eigener Chat-Kontakt Nachrichten schicken. Genau das nutzt diese Integration: Home Assistant wird zu einem Bot in deiner Kontaktliste.

## Voraussetzungen

- Home Assistant 2025.1 oder neuer
- Lethe-App auf dem Handy mit eingerichtetem Konto
- Home Assistant muss den Lethe-Server erreichen (Standard `https://letheapp.de`)

## Funktionen

- **Login per QR-Code** aus der Lethe-App (wie beim Lethe-Webclient), kein Passwort nötig.
- **Regeln in der Integration**: mehrere Entities auswählen, Bedingung festlegen, Nachrichtentext frei wählen.
  - Bedingungen: Zustand gleich / ungleich, Wert größer / kleiner, jede Änderung
  - Nachricht mit Templates: `{{ name }}`, `{{ state }}`, `{{ old_state }}`, `{{ unit }}`, `{{ entity_id }}`, `{{ attributes }}`
  - Optionaler Mindestabstand (Cooldown) pro Regel und Entity
  - Gesendet wird nur beim Übergang in die Bedingung, nicht bei jedem Attribut-Update
  - Optional: „Nur senden, wenn diese Person/dieser Tracker nicht ‚home‘ ist“ – damit lassen sich Regeln auf Abwesenheit beschränken (z. B. Präsenz-Alarme, die nur unterwegs stören sollen)
- **Notify-Entity** (`notify.send_message`) und Dienst **`lethe.send_message`** für eigene Automationen.

## Installation

**HACS:** HACS → Benutzerdefinierte Repositories → `https://github.com/thestealth131205/HA-Lethe` (Typ: Integration) → „Lethe Messenger“ installieren → Home Assistant neu starten.

**Manuell:** `custom_components/lethe` nach `<config>/custom_components/lethe` kopieren und Home Assistant neu starten.

## Einrichtung

1. Einstellungen → Geräte & Dienste → Integration hinzufügen → **Lethe Messenger**
2. Server-URL (Standard `https://letheapp.de`) und Absendername eingeben.
3. In der Lethe-App **Einstellungen → Verknüpfte Geräte → QR-Code scannen** und den angezeigten Code scannen.
4. Die Integration legt einen Bot an, startet den Chat mit dir und sendet eine Bestätigung. Die temporäre Login-Session wird danach automatisch wieder abgemeldet; dauerhaft gespeichert wird nur der Bot-Token.

Regeln anlegen: Integration → **Konfigurieren** → „Neue Regel hinzufügen“.

### Beispiele

| Entities | Bedingung | Wert | Nachricht |
|---|---|---|---|
| `binary_sensor.haustuer` | Zustand ist gleich | `on` | `🚪 Haustür wurde geöffnet` |
| `sensor.wohnzimmer_temperatur` | Wert ist kleiner als | `17` | `🥶 {{ name }}: {{ state }} {{ unit }}` |
| `binary_sensor.praesenz`, `binary_sensor.bewegung_flur` | Zustand ist gleich | `on` | `👀 Bewegung: {{ name }}` |

## Hinweis zur Verschlüsselung

Bot-Nachrichten laufen über die Lethe-Bot-API und sind – wie alle Lethe-Bot-Nachrichten – **nicht Ende-zu-Ende-verschlüsselt** (TLS-Transport, Klartext auf dem Server). Keine vertraulichen Daten in Nachrichtentexte schreiben.

## Lizenz

[GPL-3.0](LICENSE) – wie [Lethe-Community](https://github.com/thestealth131205/Lethe-Community).
