# HA-Lethe

Home-Assistant-Integration für den **Lethe Messenger**. Home Assistant schreibt dir als eigener Bot in Lethe – für Alarme, Statusmeldungen oder Infos.

## Funktionen

- **Login per QR-Code** aus der Lethe-App (wie beim Lethe-Webclient), kein Passwort nötig.
- **Regeln in der Integration**: mehrere Entities auswählen, Bedingung festlegen, Nachrichtentext frei wählen.
  - Bedingungen: Zustand gleich / ungleich, Wert größer / kleiner, jede Änderung
  - Nachricht mit Templates: `{{ name }}`, `{{ state }}`, `{{ old_state }}`, `{{ unit }}`, `{{ entity_id }}`, `{{ attributes }}`
  - Optionaler Mindestabstand (Cooldown) pro Regel und Entity
  - Gesendet wird nur beim Übergang in die Bedingung, nicht bei jedem Attribut-Update
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
