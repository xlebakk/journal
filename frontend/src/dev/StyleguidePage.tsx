/* Dev-only reference of every UI building block. Screens use only these. */
import { AlertTriangle, ChevronLeft, ChevronRight, Lock } from "lucide-react";
import { useState } from "react";

import { formatDate, formatHumanDate, formatJournalHeader, formatTime } from "@/shared/lib/time";
import { useTheme } from "@/shared/lib/theme";
import {
  AccessCards,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  EmptyState,
  FileField,
  Histogram,
  InitialsStamp,
  Notices,
  ScoreChart,
  JournalCell,
  PasswordField,
  RuledSkeleton,
  SelectField,
  StrengthMeter,
  Table,
  TextField,
  ThemeSwitch,
  LanguageSwitch,
  Logo,
  type AttendanceMark,
  ScheduleIssues,
  WeekSchedule,
  DaySchedule,
  PeriodBar,
  Segmented,
  type ScheduleItem,
} from "@/shared/ui";
import grid from "@/shared/ui/JournalGrid.module.css";

import styles from "./StyleguidePage.module.css";

const COLORS = [
  ["paper", "фон страницы"],
  ["sheet", "поверхность таблиц и форм"],
  ["ink", "основной текст"],
  ["ink-2", "вторичный текст"],
  ["rule", "линии разлиновки"],
  ["accent", "синие чернила: ссылки, фокус"],
  ["red-pen", "красная ручка: «н», низкие оценки"],
  ["pencil", "опоздания, предупреждения"],
  ["marker", "только сегодня и поиск"],
] as const;

const PEOPLE = [
  { id: "7f0c1c9e-0001", first: "Фарход", last: "Алиев" },
  { id: "7f0c1c9e-0002", first: "Мадина", last: "Каримова" },
  { id: "7f0c1c9e-0003", first: "Тимур", last: "Юсупов" },
  { id: "7f0c1c9e-0004", first: "Дильноза", last: "Рахимова" },
  { id: "7f0c1c9e-0005", first: "Сергей", last: "Ким" },
  { id: "7f0c1c9e-0006", first: "Нигора", last: "Ахмедова" },
];

type DemoCell = { grades?: number[]; attendance?: AttendanceMark };

// Ten lessons over two weeks; the column flagged `today` gets the marker.
const LESSONS = [
  { date: "09.11", type: "Лк", weekStart: true },
  { date: "11.11", type: "Пр" },
  { date: "13.11", type: "Пр" },
  { date: "14.11", type: "КР" },
  { date: "16.11", type: "Лк", weekStart: true },
  { date: "17.11", type: "Пр" },
  { date: "18.11", type: "Сем" },
  { date: "19.11", type: "Пр" },
  { date: "20.11", type: "КР" },
  { date: "21.11", type: "Пр", today: true },
];

const DEMO: DemoCell[][] = PEOPLE.map((_, row) =>
  LESSONS.map((_, col): DemoCell => {
    const seed = (row * 7 + col * 3) % 11;
    if (seed === 0) return { attendance: "absent" };
    if (seed === 5) return { attendance: "late", grades: [61] };
    if (seed === 9 && col > 6) return { attendance: "excused" };
    if (seed % 3 === 0) return { grades: [40 + seed * 5] };
    if (seed === 7) return { grades: [88, 100] };
    return {};
  }),
);

const BASE: Omit<ScheduleItem, "id" | "date" | "start_time" | "end_time" | "subject_name"> = {
  subject_short: "",
  group_name: "11-М вечерняя",
  teacher_name: "Юсупов Т.",
  room_name: "101",
  lesson_type_short: "Пр",
  status: "planned",
  cancel_reason: "",
  is_extra: false,
  is_moved: false,
  is_room_changed: false,
  is_substituted: false,
  planned_date: "2026-11-16",
  planned_start_time: "16:00:00",
  planned_room_name: "101",
};

const WEEK: ScheduleItem[] = [
  {
    ...BASE,
    id: "1",
    date: "2026-11-16",
    start_time: "16:00:00",
    end_time: "17:30:00",
    subject_name: "Математика",
  },
  {
    ...BASE,
    id: "2",
    date: "2026-11-16",
    start_time: "17:45:00",
    end_time: "19:15:00",
    subject_name: "Физика",
    status: "cancelled",
    cancel_reason: "олимпиада",
  },
  {
    ...BASE,
    id: "3",
    date: "2026-11-17",
    start_time: "16:00:00",
    end_time: "17:30:00",
    subject_name: "Английский язык",
    is_substituted: true,
    teacher_name: "Ким С.",
  },
  {
    ...BASE,
    id: "4",
    date: "2026-11-21",
    start_time: "14:00:00",
    end_time: "15:30:00",
    subject_name: "Математика",
    is_moved: true,
    planned_date: "2026-11-19",
    planned_start_time: "16:00:00",
  },
  {
    ...BASE,
    id: "5",
    date: "2026-11-21",
    start_time: "16:00:00",
    end_time: "17:30:00",
    subject_name: "Химия",
    group_name: "11-Б утренняя",
    room_name: "Актовый зал",
    is_room_changed: true,
    is_extra: true,
    lesson_type_short: "Конс",
  },
];

function JournalGridPreview() {
  const [hover, setHover] = useState<{ row: number; col: number } | null>(null);
  return (
    <div className={grid.scroller}>
      <table className={grid.grid}>
        <thead>
          <tr>
            <th className={grid.name} scope="col">
              ученик
            </th>
            {LESSONS.map((lesson, col) => (
              <th
                key={lesson.date}
                scope="col"
                className={[
                  grid.dataCell,
                  lesson.weekStart && grid.weekStart,
                  lesson.today && grid.today,
                  hover?.col === col && grid.hover,
                ]
                  .filter(Boolean)
                  .join(" ")}
              >
                {lesson.date}
                <br />
                {lesson.type}
              </th>
            ))}
            <th className={grid.summary} scope="col">
              ср.
            </th>
          </tr>
        </thead>
        <tbody>
          {PEOPLE.map((person, row) => (
            <tr key={person.id}>
              <th
                scope="row"
                className={[grid.name, hover?.row === row && grid.hover].filter(Boolean).join(" ")}
              >
                {person.last} {person.first.charAt(0)}.
              </th>
              {LESSONS.map((lesson, col) => {
                const cell = DEMO[row]?.[col] ?? {};
                const highlighted = hover !== null && (hover.row === row || hover.col === col);
                return (
                  <td
                    key={lesson.date}
                    onMouseEnter={() => setHover({ row, col })}
                    onMouseLeave={() => setHover(null)}
                    className={[
                      grid.dataCell,
                      lesson.weekStart && grid.weekStart,
                      lesson.today && grid.today,
                      highlighted && grid.hover,
                      row === 1 && col === 7 && grid.selected,
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <JournalCell lowBelow={50} {...cell} />
                  </td>
                );
              })}
              <td className={grid.summary}>{(62 + row * 5.37).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function StyleguidePage() {
  const [theme, setTheme] = useTheme();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [password, setPassword] = useState("зелёный чай");
  const [view, setView] = useState<"week" | "requests">("week");
  const [periodMonday, setPeriodMonday] = useState("2026-11-16");
  const now = new Date();

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <span className={styles.brand}>Учебный центр</span>
        <span className={styles.tag}>/dev/styleguide</span>
        <ThemeSwitch value={theme} onChange={setTheme} />
        <LanguageSwitch />
      </header>

      <main className={styles.main}>
        <h1>Стайлгайд</h1>
        <p className={styles.lead}>
          «Журнал, а не дэшборд». Экраны собираются только из этих компонентов.
        </p>

        <section className={styles.section} aria-labelledby="sg-logo">
          <h2 id="sg-logo">Логотип</h2>
          <p>
            Daftar — «тетрадь, журнал»: название программы, не центра. Страница журнала с полем,
            линейками и красной закладкой; цвета из токенов. В шапке — обычный размер, на входе —
            крупный с подписью. Иконки приложения рисует mobile/scripts/make_icons.py.
          </p>
          <div className={styles.row}>
            <Logo />
            <Logo size="lg" tagline />
          </div>
        </section>

        <section className={styles.section} aria-labelledby="sg-colors">
          <h2 id="sg-colors">Цвета</h2>
          <ul className={styles.swatches}>
            {COLORS.map(([token, purpose]) => (
              <li key={token} className={styles.swatch}>
                <span className={`${styles.chip} ${styles[`chip-${token}`]}`} />
                <code className="mono">--{token}</code>
                <span className={styles.caption}>{purpose}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className={styles.section} aria-labelledby="sg-type">
          <h2 id="sg-type">Шрифты</h2>
          <p className={styles.display}>Golos Text 700 — Алиев Фарход Рустамович</p>
          <p>Golos Text 400 — весь интерфейс, текст из нескольких строк с интервалом 1.45.</p>
          <p className={styles.medium}>Golos Text 500 — подписи вкладок и кнопок</p>
          <p className={styles.semibold}>Golos Text 600 — подзаголовки</p>
          <p className="mono">
            JetBrains Mono — {formatJournalHeader(now)} · {formatTime(now)} · aliev.f · 87 / 100
          </p>
          <p className={styles.caption}>
            Человеческая дата: {formatHumanDate(now)}. Цифровая: {formatDate(now)}.
          </p>
          <ol className={styles.scale}>
            {[12, 14, 15, 16, 20, 28, 40].map((size) => (
              <li key={size} className={styles[`size-${size}`]}>
                {size} — Журнал
              </li>
            ))}
          </ol>
        </section>

        <section className={styles.section} aria-labelledby="sg-buttons">
          <h2 id="sg-buttons">Кнопки</h2>
          <div className={styles.row}>
            <Button variant="primary">завершить занятие</Button>
            <Button>все присутствуют</Button>
            <Button variant="danger">удалить оценку</Button>
            <Button disabled>недоступно</Button>
            <Button aria-label="Предыдущая неделя">
              <ChevronLeft size={18} strokeWidth={1.5} aria-hidden="true" />
            </Button>
            <Button aria-label="Следующая неделя">
              <ChevronRight size={18} strokeWidth={1.5} aria-hidden="true" />
            </Button>
          </div>
        </section>

        <section className={styles.section} aria-labelledby="sg-fields">
          <h2 id="sg-fields">Поля</h2>
          <div className={styles.fields}>
            <TextField label="Логин" defaultValue="aliev.f" autoComplete="off" />
            <TextField label="Тема занятия" placeholder="Квадратные уравнения" />
            <TextField label="Оценка" inputMode="numeric" defaultValue="104" error="От 0 до 100" />
            <TextField label="Пароль" type="password" hint="Не короче 10 символов" />
            <div>
              <PasswordField
                label="Новый пароль"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <StrengthMeter password={password} personal={["aliev.f"]} />
            </div>
            <SelectField
              label="Класс"
              defaultValue="11"
              options={[
                { value: "9", label: "9" },
                { value: "10", label: "10" },
                { value: "11", label: "11" },
              ]}
            />
            <Checkbox label="Запомнить это устройство" />
          </div>
        </section>

        <section className={styles.section} aria-labelledby="sg-table">
          <h2 id="sg-table">Таблица</h2>
          <Table>
            <thead>
              <tr>
                <th scope="col">предмет</th>
                <th scope="col">средний балл</th>
                <th scope="col">посещаемость</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Математика</td>
                <td className="mono">78.40</td>
                <td className="mono">92%</td>
              </tr>
              <tr>
                <td>Физика</td>
                <td className={`mono ${styles.low}`}>46.15</td>
                <td className={`mono ${styles.low}`}>74%</td>
              </tr>
              <tr>
                <td>Английский язык</td>
                <td className="mono">85.00</td>
                <td className="mono">100%</td>
              </tr>
            </tbody>
          </Table>
        </section>

        <section className={styles.section} aria-labelledby="sg-grid">
          <h2 id="sg-grid">Ячейки журнала</h2>
          <p className={styles.caption}>
            Красная линия полей, маркер сегодняшнего дня, граница недели, подсветка строки и столбца
            при наведении, выбранная ячейка. Низкие оценки (&lt; 50) — красной ручкой.
          </p>
          <JournalGridPreview />
        </section>

        <section className={styles.section} aria-labelledby="sg-stamp">
          <h2 id="sg-stamp">Штамп инициалов</h2>
          <div className={styles.row}>
            {PEOPLE.map((person) => (
              <InitialsStamp
                key={person.id}
                userId={person.id}
                firstName={person.first}
                lastName={person.last}
              />
            ))}
          </div>
        </section>

        <section className={styles.section} aria-labelledby="sg-week">
          <h2 id="sg-week">Расписание недели</h2>
          <p className={styles.caption}>
            Строки — время начала, колонки — дни. Отмена зачёркнута, перенос, замена и кабинет —
            текстом. На телефоне — список по дням.
          </p>
          <WeekSchedule
            monday="2026-11-16"
            today="2026-11-21"
            lessons={WEEK}
            showGroup
            showTeacher
          />
          <ScheduleIssues
            conflicts={[
              {
                kind: "room",
                date: "2026-11-16",
                start_time: "16:00",
                end_time: "17:30",
                group: "11-Г вечерняя",
                subject: "Английский язык",
                teacher: "Ким С.",
                room: "101",
              },
            ]}
            warnings={[{ kind: "students", date: "2026-11-21", students: ["Алиев Ф.", "Ким М."] }]}
          />
        </section>

        <section className={styles.section} aria-labelledby="sg-days">
          <h2 id="sg-days">Расписание по дням</h2>
          <p className={styles.caption}>
            Как в eDonish: переключатель видов, «выбор периода» — широкая таблетка со стрелками,
            плитки дней; выбранная темнее и подчёркнута, её уроки — на белой панели под ней.
          </p>
          <Segmented
            label="Вид"
            value={view}
            onChange={setView}
            options={[
              { value: "week", label: "Моё расписание" },
              { value: "requests", label: "Мои запросы (1)" },
            ]}
          />
          <PeriodBar monday={periodMonday} today="2026-11-21" onChange={setPeriodMonday} />
          <DaySchedule monday="2026-11-16" today="2026-11-21" lessons={WEEK} showGroup />
        </section>

        <section className={styles.section} aria-labelledby="sg-charts">
          <h2 id="sg-charts">Графики</h2>
          <p className={styles.caption}>
            Результаты пробных тестов — в процентах от максимума, над точкой — балл; цель — пунктир.
            Распределение — по 10 % максимума. Только SVG и цвета из токенов.
          </p>
          <ScoreChart
            label="Математика: результаты пробных тестов"
            target={80}
            targetLabel="цель 80%"
            points={[
              { key: "1", label: "05.10", percent: 63.3, score: "19 / 30" },
              { key: "2", label: "26.10", percent: 76.7, score: "23 / 30" },
              { key: "3", label: "09.11", percent: null, score: "не был" },
              { key: "4", label: "16.11", percent: 84, score: "84 / 100" },
            ]}
          />
          <Histogram
            label="Распределение результатов"
            buckets={[0, 1, 0, 2, 4, 6, 9, 7, 3, 1].map((count, i) => ({
              key: String(i),
              label: `${i * 10}–${i === 9 ? 100 : i * 10 + 9}`,
              count,
            }))}
          />
        </section>

        <section className={styles.section} aria-labelledby="sg-notices">
          <h2 id="sg-notices">Объявления и файлы</h2>
          <Notices
            pinnedLabel="закреплено"
            items={[
              {
                id: "1",
                title: "Зимние каникулы",
                body: "С 30 декабря по 8 января занятий нет. Подробности: https://example.com/rules",
                pinned: true,
                published_at: "2026-11-20T09:00:00Z",
                author_name: "Каримова Д.",
              },
              {
                id: "2",
                title: "Пробный ДТМ № 4",
                body: "В субботу в 10:00, кабинет 201.",
                pinned: false,
                published_at: "2026-11-18T12:30:00Z",
                author_name: "Каримова Д.",
              },
            ]}
          />
          <FileField label="Файл XLSX или CSV" hint="До 5 МБ." accept=".xlsx,.csv" />
        </section>

        <section className={styles.section} aria-labelledby="sg-cards">
          <h2 id="sg-cards">Карточки доступа</h2>
          <p className={styles.caption}>
            Лист A4 по 8 карточек; пароль виден только на этой странице, потом — только сброс.
          </p>
          <AccessCards
            centerName="Учебный центр"
            siteUrl="https://journal.example.com"
            qr="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSI3MiIgaGVpZ2h0PSI3MiI+PHJlY3Qgd2lkdGg9IjcyIiBoZWlnaHQ9IjcyIiBmaWxsPSIjZGRkIi8+PC9zdmc+"
            labels={{
              login: "Логин",
              password: "Пароль",
              site: "Сайт",
              note: "При первом входе система попросит сменить пароль.",
            }}
            cards={[
              {
                id: "a",
                full_name: "Алиев Фарход Рустамович",
                login: "aliev.f",
                temporary_password: "hK7mPq2xRt9z",
                group_name: "11-М вечерняя",
              },
              {
                id: "b",
                full_name: "Ганиева Мадина",
                login: "ganieva.m",
                temporary_password: "Wn4bTe8sLp3d",
                group_name: "11-М вечерняя",
              },
            ]}
          />
        </section>

        <section className={styles.section} aria-labelledby="sg-states">
          <h2 id="sg-states">Состояния и иконки</h2>
          <RuledSkeleton rows={3} />
          <EmptyState text="На сегодня занятий нет." action={<a href="#sg-grid">к журналу</a>} />
          <p className={styles.iconRow}>
            <Lock size={16} strokeWidth={1.5} aria-hidden="true" /> Изменить может администратор
          </p>
          <p className={`${styles.iconRow} ${styles.warning}`}>
            <AlertTriangle size={16} strokeWidth={1.5} aria-hidden="true" /> Не сохранено —
            повторить
          </p>
        </section>

        <section className={styles.section} aria-labelledby="sg-modal">
          <h2 id="sg-modal">Модальное окно</h2>
          <p>
            <Button onClick={() => setDialogOpen(true)}>открыть диалог</Button>
          </p>
          <Dialog
            open={dialogOpen}
            onOpenChange={setDialogOpen}
            title="Подтвердите пароль"
            description="Для этого действия нужно ещё раз ввести пароль."
          >
            <PasswordField label="Пароль" />
            <DialogActions>
              <Button variant="primary" onClick={() => setDialogOpen(false)}>
                подтвердить
              </Button>
              <Button onClick={() => setDialogOpen(false)}>отмена</Button>
            </DialogActions>
          </Dialog>
          <div className={styles.modal} role="presentation">
            <h3>Завершить занятие?</h3>
            <p>Тема и посещаемость заполнены. Оценки можно добавить позже.</p>
            <div className={styles.row}>
              <Button variant="primary">завершить</Button>
              <Button>отмена</Button>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
