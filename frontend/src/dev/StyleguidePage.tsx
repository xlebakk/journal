/* Dev-only reference of every UI building block (SPEC §12). Screens use only these. */
import { AlertTriangle, ChevronLeft, ChevronRight, Lock } from "lucide-react";
import { useState } from "react";

import { formatDate, formatHumanDate, formatJournalHeader, formatTime } from "@/shared/lib/time";
import { useTheme } from "@/shared/lib/theme";
import {
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  EmptyState,
  InitialsStamp,
  JournalCell,
  PasswordField,
  RuledSkeleton,
  SelectField,
  StrengthMeter,
  Table,
  TextField,
  ThemeSwitch,
  type AttendanceMark,
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
  const now = new Date();

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <span className={styles.brand}>Учебный центр</span>
        <span className={styles.tag}>/dev/styleguide</span>
        <ThemeSwitch value={theme} onChange={setTheme} />
      </header>

      <main className={styles.main}>
        <h1>Стайлгайд</h1>
        <p className={styles.lead}>
          «Журнал, а не дэшборд». Экраны собираются только из этих компонентов.
        </p>

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
          <p className={styles.display}>Literata 600 — Алиев Фарход Рустамович</p>
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
