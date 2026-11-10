#!/usr/bin/env python3
"""Language-table entries for the Remastered HUD (ui-visual-design.md 14).

The Remastered HUD documents and the game's Remastered fields use the
#str_2312xx block. Running this script adds missing entries to every
content/baseoq4/pak0/strings/*_openq4.lang table (UTF-8, CRLF) and updates
entries whose text changed; `--check` reports tables that are out of date.

Ordinals: #str_231201 is first place exactly, then 231202-231205 are the
places ending in 1, 2 and 3 (not 11-13) and every other place, each a format
with one %d.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STRINGS = ROOT / "content/baseoq4/pak0/strings"
LANGUAGES = ("english", "brazilian", "czech", "french", "german", "hungarian", "italian", "polish", "russian", "spanish",
             "turkish", "ukrainian")

# key: (english, brazilian, czech, french, german, hungarian, italian, polish, russian, spanish, turkish, ukrainian)
ENTRIES = {
    "#str_231326": ("AIR", "AR", "VZDUCH", "AIR", "LUFT", "LEVEGŐ", "ARIA", "POWIETRZE", "ВОЗДУХ", "AIRE", "HAVA", "ПОВІТРЯ"),
    "#str_231325": ("%d m", "%d m", "%d m", "%d m", "%d m", "%d m", "%d m", "%d m", "%d м", "%d m", "%d m", "%d м"),
    "#str_231200": ("TIED", "EMPATE", "REMÍZA", "ÉGALITÉ", "GLEICHSTAND", "DÖNTETLEN", "PARI", "REMIS", "НИЧЬЯ", "EMPATE",
                    "BERABERE", "НІЧИЯ"),
    "#str_231201": ("%dST", "%dº", "%d.", "%dER", "%d.", "%d.", "%dº", "%d.", "%d-Е", "%dº", "%d.", "%d-Е"),
    "#str_231202": ("%dST", "%dº", "%d.", "%dE", "%d.", "%d.", "%dº", "%d.", "%d-Е", "%dº", "%d.", "%d-Е"),
    "#str_231203": ("%dND", "%dº", "%d.", "%dE", "%d.", "%d.", "%dº", "%d.", "%d-Е", "%dº", "%d.", "%d-Е"),
    "#str_231204": ("%dRD", "%dº", "%d.", "%dE", "%d.", "%d.", "%dº", "%d.", "%d-Е", "%dº", "%d.", "%d-Е"),
    "#str_231205": ("%dTH", "%dº", "%d.", "%dE", "%d.", "%d.", "%dº", "%d.", "%d-Е", "%dº", "%d.", "%d-Е"),
    "#str_231206": ("WARM-UP", "AQUECIMENTO", "ROZCVIČKA", "ÉCHAUFFEMENT", "AUFWÄRMEN", "BEMELEGÍTÉS", "RISCALDAMENTO",
                    "ROZGRZEWKA", "РАЗМИНКА", "CALENTAMIENTO", "ISINMA", "РОЗМИНКА"),
    "#str_231207": ("STARTS IN", "COMEÇA EM", "ZAČÁTEK ZA", "DÉBUT DANS", "START IN", "KEZDÉS", "INIZIO TRA", "START ZA",
                    "СТАРТ ЧЕРЕЗ", "EMPIEZA EN", "BAŞLAMAYA", "СТАРТ ЧЕРЕЗ"),
    "#str_231208": ("SUDDEN DEATH", "MORTE SÚBITA", "NÁHLÁ SMRT", "MORT SUBITE", "SUDDEN DEATH", "HIRTELEN HALÁL",
                    "MORTE IMPROVVISA", "NAGŁA ŚMIERĆ", "ВНЕЗАПНАЯ СМЕРТЬ", "MUERTE SÚBITA", "ANİ ÖLÜM", "РАПТОВА СМЕРТЬ"),
    "#str_231209": ("VOTE", "VOTAÇÃO", "HLASOVÁNÍ", "VOTE", "ABSTIMMUNG", "SZAVAZÁS", "VOTAZIONE", "GŁOSOWANIE", "ГОЛОСОВАНИЕ",
                    "VOTACIÓN", "OYLAMA", "ГОЛОСУВАННЯ"),
    "#str_231210": ("YES", "SIM", "ANO", "OUI", "JA", "IGEN", "SÌ", "TAK", "ДА", "SÍ", "EVET", "ТАК"),
    "#str_231211": ("NO", "NÃO", "NE", "NON", "NEIN", "NEM", "NO", "NIE", "НЕТ", "NO", "HAYIR", "НІ"),
    "#str_231212": ("FOLLOWING", "SEGUINDO", "SLEDUJETE", "SUIVI", "FOLGEN", "KÖVETÉS", "SEGUI", "OBSERWUJESZ", "НАБЛЮДЕНИЕ",
                    "SIGUIENDO", "TAKİP", "СПОСТЕРЕЖЕННЯ"),
    "#str_231213": ("SPECTATING", "ESPECTADOR", "DIVÁK", "SPECTATEUR", "ZUSCHAUER", "NÉZŐ", "SPETTATORE", "WIDZ", "ЗРИТЕЛЬ",
                    "ESPECTADOR", "İZLEYİCİ", "ГЛЯДАЧ"),
    "#str_231214": ("Free camera", "Câmera livre", "Volná kamera", "Caméra libre", "Freie Kamera", "Szabad kamera",
                    "Telecamera libera", "Wolna kamera", "Свободная камера", "Cámara libre", "Serbest kamera", "Вільна камера"),
    "#str_231215": ("Next", "Próximo", "Další", "Suivant", "Weiter", "Következő", "Successivo", "Następny", "Далее",
                    "Siguiente", "Sonraki", "Далі"),
    "#str_231216": ("Follow a player", "Seguir um jogador", "Sledovat hráče", "Suivre un joueur", "Spieler folgen",
                    "Játékos követése", "Segui un giocatore", "Obserwuj gracza", "Следить за игроком", "Seguir a un jugador",
                    "Bir oyuncuyu izle", "Стежити за гравцем"),
    "#str_231217": ("Scores", "Placar", "Skóre", "Scores", "Punkte", "Eredmények", "Punteggi", "Wyniki", "Счёт", "Puntuaciones",
                    "Skorlar", "Рахунок"),
    "#str_231218": ("ZONE", "ZONA", "ZÓNA", "ZONE", "ZONE", "ZÓNA", "ZONA", "STREFA", "ЗОНА", "ZONA", "BÖLGE", "ЗОНА"),
    "#str_231219": ("CONTESTED", "DISPUTADA", "SPORNÁ", "DISPUTÉE", "UMKÄMPFT", "VITATOTT", "CONTESA", "SPORNA", "ОСПАРИВАЕТСЯ",
                    "EN DISPUTA", "ÇEKİŞMELİ", "ОСКАРЖУЄТЬСЯ"),
    "#str_231220": ("EMPTY", "VAZIA", "PRÁZDNÁ", "VIDE", "LEER", "ÜRES", "VUOTA", "PUSTA", "ПУСТО", "VACÍA", "BOŞ", "ПОРОЖНЬО"),
    "#str_231221": ("YOU", "VOCÊ", "VY", "VOUS", "DU", "TE", "TU", "TY", "ВЫ", "TÚ", "SEN", "ВИ"),
    # Symbols the HUD composes around numbers and names; the same in every language.
    "#str_231222": ("/",) * 12,
    "#str_231223": ("+",) * 12,
    # The deficit sign: an en dash, which every font page carries (U+2212 lies outside the
    # blocks the font rasteriser builds; tools/tests/lang_table_encoding.py).
    "#str_231224": ("–",) * 12,
    "#str_231225": ("!",) * 12,
    "#str_231226": ("?",) * 12,
    "#str_231227": (": ",) * 12,
    "#str_231228": ("ms",) * 12,
    # The vehicle HUD prompt (14.8): leaving a vehicle or gun, and a locked one.
    "#str_231229": ("Exit", "Sair", "Opustit", "Sortir", "Verlassen", "Kilépés", "Esci", "Wyjdź", "Выйти", "Salir", "Çık",
                    "Вийти"),
    "#str_231230": ("Vehicle locked", "Veículo travado", "Vozidlo zamčeno", "Véhicule verrouillé", "Fahrzeug gesperrt",
                    "Jármű zárolva", "Veicolo bloccato", "Pojazd zablokowany", "Транспорт заблокирован", "Vehículo bloqueado",
                    "Araç kilitli", "Транспорт заблоковано"),
    # The scoreboard (14.14): the bot tag and your place, an ordinal (231201-231205) of the players.
    "#str_231231": ("BOT", "BOT", "BOT", "BOT", "BOT", "BOT", "BOT", "BOT", "БОТ", "BOT", "BOT", "БОТ"),
    "#str_231232": ("%s OF %d", "%s DE %d", "%s Z %d", "%s SUR %d", "%s VON %d", "%s / %d", "%s SU %d", "%s Z %d", "%s ИЗ %d",
                    "%s DE %d", "%s / %d", "%s З %d"),
    # The multiplayer respawn prompt (14.9): the attack control's action, and the hold's countdown label.
    "#str_231233": ("Respawn", "Renascer", "Oživit", "Réapparaître", "Wiedereinstieg", "Újraéledés", "Rinasci", "Odrodzenie",
                    "Возродиться", "Reaparecer", "Yeniden doğ", "Відродитися"),
    "#str_231234": ("RESPAWN IN", "RENASCE EM", "OŽIVENÍ ZA", "RÉAPPARITION DANS", "WIEDEREINSTIEG IN", "ÚJRAÉLEDÉSIG",
                    "RINASCITA TRA", "ODRODZENIE ZA", "ВОЗРОЖДЕНИЕ ЧЕРЕЗ", "REAPARICIÓN EN", "YENİDEN DOĞMAYA",
                    "ВІДРОДЖЕННЯ ЧЕРЕЗ"),
    # Settings > Game Options > HUD (section 13.9): the section label, its rows and their choices.
    "#str_231235": ("HUD",) * 12,
    "#str_231236": ("HUD Layout", "Layout do HUD", "Rozložení HUD", "Disposition du HUD", "HUD-Layout", "HUD elrendezés",
                    "Layout HUD", "Układ HUD", "Макет HUD", "Diseño del HUD", "HUD düzeni", "Макет HUD"),
    "#str_231237": ("Classic;Remastered;Minimal;Competitive", "Clássico;Remasterizado;Mínimo;Competitivo",
                    "Klasické;Remasterované;Minimální;Soutěžní", "Classique;Remasterisé;Minimal;Compétitif",
                    "Klassisch;Remastered;Minimal;Kompetitiv", "Klasszikus;Felújított;Minimális;Versenyző",
                    "Classico;Rimasterizzato;Minimo;Competitivo", "Klasyczny;Odnowiony;Minimalny;Turniejowy",
                    "Классический;Ремастер;Минимальный;Соревновательный", "Clásico;Remasterizado;Mínimo;Competitivo",
                    "Klasik;Yenilenmiş;Minimal;Rekabetçi", "Класичний;Ремастер;Мінімальний;Змагальний"),
    "#str_231238": ("HUD Size", "Tamanho do HUD", "Velikost HUD", "Taille du HUD", "HUD-Größe", "HUD méret", "Dimensione HUD",
                    "Rozmiar HUD", "Размер HUD", "Tamaño del HUD", "HUD boyutu", "Розмір HUD"),
    "#str_231239": ("HUD Width", "Largura do HUD", "Šířka HUD", "Largeur du HUD", "HUD-Breite", "HUD szélesség",
                    "Larghezza HUD", "Szerokość HUD", "Ширина HUD", "Ancho del HUD", "HUD genişliği", "Ширина HUD"),
    "#str_231240": ("16:9;21:9;Full", "16:9;21:9;Total", "16:9;21:9;Celá", "16:9;21:9;Plein", "16:9;21:9;Voll",
                    "16:9;21:9;Teljes", "16:9;21:9;Piena", "16:9;21:9;Pełna", "16:9;21:9;Вся", "16:9;21:9;Completa",
                    "16:9;21:9;Tam", "16:9;21:9;Уся"),
    # The MCC cannon's readout (14.12): the ship's name, the same in every language.
    "#str_231242": ("U.S.S.",) * 12,
    "#str_231243": ("Hannibal",) * 12,
    "#str_231241": ("Safe Area Inset", "Margem da área segura", "Okraj bezpečné oblasti", "Marge de zone sûre",
                    "Sicherheitsrand", "Biztonsági margó", "Margine area sicura", "Margines obszaru bezpiecznego",
                    "Отступ безопасной зоны", "Margen de zona segura", "Güvenli alan boşluğu", "Відступ безпечної зони"),
    # The speeder bike (14.12): the boost in the HUD prompt, and the race
    # timer's decimal separator.
    "#str_231244": ("Boost", "Acelerar", "Zrychlit", "Accélérer", "Boost", "Turbó", "Accelera", "Przyspiesz", "Ускориться",
                    "Acelerar", "Hızlan", "Прискоритися"),
    "#str_231245": ("Boosting", "Acelerando", "Zrychlení", "Accélération", "Boost aktiv", "Turbó aktív", "Accelerazione",
                    "Przyspieszanie", "Ускорение", "Acelerando", "Hızlanıyor", "Прискорення"),
    "#str_231246": (".", ",", ",", ",", ",", ",", ",", ",", ",", ",", ",", ","),
    # The Competitive match bar (14.9): the limit under the timer, the Tourney
    # round tag and the warm-up's ready count.
    "#str_231248": ("TO %s", "ATÉ %s", "DO %s", "EN %s", "BIS %s", "CÉL %s", "A %s", "DO %s", "ДО %s", "A %s", "HEDEF %s",
                    "ДО %s"),
    "#str_231249": ("R%s", "R%s", "K%s", "M%s", "R%s", "F%s", "T%s", "R%s", "Р%s", "R%s", "T%s", "Р%s"),
    "#str_231250": ("READY %s/%s", "PRONTOS %s/%s", "PŘIPRAVENO %s/%s", "PRÊTS %s/%s", "BEREIT %s/%s", "KÉSZ %s/%s",
                    "PRONTI %s/%s", "GOTOWI %s/%s", "ГОТОВЫ %s/%s", "LISTOS %s/%s", "HAZIR %s/%s", "ГОТОВІ %s/%s"),
    # Under the Competitive match bar: each team's flag (14.9).
    "#str_231251": ("AT BASE", "NA BASE", "NA ZÁKLADNĚ", "À LA BASE", "IN DER BASIS", "BÁZISON", "ALLA BASE", "W BAZIE",
                    "НА БАЗЕ", "EN LA BASE", "ÜSTE", "НА БАЗІ"),
    "#str_231252": ("TAKEN", "ROUBADA", "UKRADENA", "PRIS", "GESTOHLEN", "ELLOPVA", "RUBATA", "SKRADZIONA", "ЗАХВАЧЕН",
                    "ROBADA", "ALINDI", "ЗАХОПЛЕНО"),
    "#str_231253": ("DROPPED", "CAÍDA", "UPUŠTĚNA", "TOMBÉ", "AM BODEN", "ELEJTVE", "A TERRA", "UPUSZCZONA", "БРОШЕН",
                    "CAÍDA", "DÜŞTÜ", "КИНУТО"),
    # The chat input (14.9): the All channel's tag (the Team tag is #str_231001)
    # and the Send and Channel prompts (Cancel is #str_42936).
    "#str_231254": ("ALL", "TODOS", "VŠICHNI", "TOUS", "ALLE", "MIND", "TUTTI", "WSZYSCY", "ВСЕ", "TODOS", "HERKES", "УСІ"),
    "#str_231255": ("Send", "Enviar", "Odeslat", "Envoyer", "Senden", "Küldés", "Invia", "Wyślij", "Отправить", "Enviar", "Gönder",
                    "Надіслати"),
    "#str_231256": ("Channel", "Canal", "Kanál", "Canal", "Kanal", "Csatorna", "Canale", "Kanał", "Канал", "Canal", "Kanal", "Канал"),
    # The match summary's way back with the active device's key (14.14).
    "#str_231257": ("[ Press %s to return to the game ]", "[ Pressione %s para voltar ao jogo ]",
                    "[ Stiskněte %s pro návrat do hry ]", "[ Appuyez sur %s pour revenir au jeu ]",
                    "[ Drücke %s, um zum Spiel zurückzukehren ]", "[ Nyomd meg: %s – vissza a játékba ]",
                    "[ Premi %s per tornare al gioco ]", "[ Naciśnij %s, aby wrócić do gry ]",
                    "[ Нажмите %s, чтобы вернуться в игру ]", "[ Pulsa %s para volver al juego ]",
                    "[ Oyuna dönmek için %s tuşuna bas ]", "[ Натисніть %s, щоб повернутися до гри ]"),
    # The held scoreboard's count of the rows below while it scrolls (14.14).
    "#str_231258": ("%d MORE", "MAIS %d", "DALŠÍ: %d", "%d DE PLUS", "NOCH %d", "MÉG %d", "ANCORA %d", "JESZCZE %d", "ЕЩЁ %d",
                    "%d MÁS", "%d DAHA", "ЩЕ %d"),
    # The match summary card's empty chat field (14.14).
    "#str_231259": ("Send a message", "Enviar uma mensagem", "Odeslat zprávu", "Envoyer un message", "Nachricht senden",
                    "Üzenet küldése", "Invia un messaggio", "Wyślij wiadomość", "Отправить сообщение", "Enviar un mensaje",
                    "Mesaj gönder", "Надіслати повідомлення"),
    # Its prompt bar's Channel, in capitals as the card's other verbs.
    "#str_231260": ("CHANNEL", "CANAL", "KANÁL", "CANAL", "KANAL", "CSATORNA", "CANALE", "KANAŁ", "КАНАЛ", "CANAL", "KANAL", "КАНАЛ"),
    # The quick-chat wheel's phrases (14.6), clockwise from the top: the
    # team calls first, then the courtesies. The sender's language is sent.
    "#str_231261": ("Attack!", "Atacar!", "Útok!", "Attaquez!", "Angriff!", "Támadás!", "Attacco!", "Atak!", "Атакуем!", "¡Atacad!",
                    "Saldırın!", "Атакуємо!"),
    "#str_231262": ("Defend!", "Defender!", "Bránit!", "Défendez!", "Verteidigen!", "Védekezés!", "Difesa!", "Obrona!",
                    "Обороняемся!", "¡Defended!", "Savunun!", "Обороняємося!"),
    "#str_231263": ("Need backup!", "Preciso de apoio!", "Potřebuju posily!", "Besoin de renfort!", "Brauche Verstärkung!",
                    "Erősítés kell!", "Serve rinforzo!", "Potrzebuję wsparcia!", "Нужна помощь!", "¡Necesito refuerzos!",
                    "Desteğe ihtiyacım var!", "Потрібна допомога!"),
    "#str_231264": ("Enemy incoming!", "Inimigo chegando!", "Nepřítel se blíží!", "Ennemi en approche!", "Feind im Anmarsch!",
                    "Ellenség közeleg!", "Nemico in arrivo!", "Wróg nadchodzi!", "Враг приближается!", "¡Enemigo en camino!",
                    "Düşman geliyor!", "Ворог наближається!"),
    "#str_231265": ("On my way!", "A caminho!", "Jsem na cestě!", "J'arrive!", "Bin unterwegs!", "Úton vagyok!", "Arrivo!", "Już idę!",
                    "Уже иду!", "¡Voy para allá!", "Geliyorum!", "Вже йду!"),
    "#str_231266": ("Thanks!", "Valeu!", "Díky!", "Merci!", "Danke!", "Köszi!", "Grazie!", "Dzięki!", "Спасибо!", "¡Gracias!",
                    "Teşekkürler!", "Дякую!"),
    "#str_231267": ("Nice shot!", "Belo tiro!", "Pěkná rána!", "Joli tir!", "Guter Schuss!", "Szép lövés!", "Bel colpo!",
                    "Niezły strzał!", "Отличный выстрел!", "¡Buen tiro!", "Güzel atış!", "Чудовий постріл!"),
    "#str_231268": ("Good game!", "Bom jogo!", "Dobrá hra!", "Bien joué!", "Gutes Spiel!", "Jó játék!", "Bella partita!", "Dobra gra!",
                    "Хорошая игра!", "¡Buena partida!", "İyi oyundu!", "Гарна гра!"),
    # Settings > Game Options > HUD (13.9): opacity and the optional groups.
    "#str_231270": ("HUD Opacity", "Opacidade do HUD", "Neprůhlednost HUD", "Opacité du HUD", "HUD-Deckkraft", "HUD átlátszatlansága",
                    "Opacità HUD", "Nieprzezroczystość HUD", "Непрозрачность HUD", "Opacidad del HUD", "HUD Opaklığı", "Непрозорість HUD"),
    "#str_231271": ("Damage Direction", "Direção do dano", "Směr poškození", "Direction des dégâts", "Schadensrichtung", "Sebzés iránya",
                    "Direzione del danno", "Kierunek obrażeń", "Направление урона", "Dirección del daño", "Hasar Yönü", "Напрямок шкоди"),
    "#str_231272": ("Pickup Messages", "Mensagens de coleta", "Zprávy o sebrání", "Messages de ramassage", "Aufnahmemeldungen",
                    "Felvételi üzenetek", "Messaggi di raccolta", "Komunikaty o podniesieniu", "Сообщения о подборе", "Mensajes de recogida",
                    "Toplama Mesajları", "Повідомлення про підбір"),
    "#str_231273": ("Weapon Strip", "Barra de armas", "Pruh zbraní", "Barre d'armes", "Waffenleiste", "Fegyversáv", "Barra delle armi",
                    "Pasek broni", "Полоса оружия", "Barra de armas", "Silah Şeridi", "Смуга зброї"),
    # Settings > Controls: the quick-chat wheel's hold action (_quickChat).
    "#str_231269": ("Quick Chat", "Chat rápido", "Rychlý chat", "Chat rapide", "Schnellchat", "Gyors csevegés", "Chat rapida",
                    "Szybki czat", "Быстрый чат", "Chat rápido", "Hızlı sohbet", "Швидкий чат"),
    # Settings > Game Options > HUD: the objectives display's hold or toggle (14.11).
    "#str_231247": ("Toggle Objectives", "Alternar objetivos", "Přepínání úkolů", "Objectifs à bascule", "Ziele umschalten",
                    "Célok be/ki", "Obiettivi a commutazione", "Przełącz cele", "Переключать задачи", "Alternar objetivos",
                    "Görevleri aç/kapat", "Перемикання завдань"),
}

LINE = re.compile(r'^\s*"(#str_\d+)"\s*"(.*)"\s*$')


def update(path: Path, language: str, check: bool) -> bool:
    raw = path.read_bytes().decode("utf-8")
    lines = raw.replace("\r\n", "\n").split("\n")
    index = LANGUAGES.index(language)
    present = {}
    for i, line in enumerate(lines):
        match = LINE.match(line)
        if match:
            present[match.group(1)] = i
    changed = False
    additions = []
    for key, values in ENTRIES.items():
        text = values[index].replace('"', '\\"')
        entry = f'\t"{key}"\t"{text}"'
        if key in present:
            if lines[present[key]] != entry:
                lines[present[key]] = entry
                changed = True
        else:
            additions.append(entry)
    if additions:
        close = max(i for i, line in enumerate(lines) if line.strip() == "}")
        lines[close:close] = additions
        changed = True
    if changed and not check:
        path.write_bytes("\r\n".join(lines).encode("utf-8"))
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    stale = [language for language in LANGUAGES if update(STRINGS / f"{language}_openq4.lang", language, args.check)]
    if args.check and stale:
        print("stale language tables:", ", ".join(stale))
        return 1
    print("updated:" if stale else "current", ", ".join(stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
