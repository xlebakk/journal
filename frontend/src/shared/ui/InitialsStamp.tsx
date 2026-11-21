import { forwardRef, type ButtonHTMLAttributes } from "react";

import { t } from "@/shared/i18n";

import styles from "./InitialsStamp.module.css";
import { initialsOf, stampInk } from "./stamp";

type InitialsStampProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  userId: string;
  firstName: string;
  lastName: string;
};

/** 32×32 square stamp in the header corner. Not a circle. */
export const InitialsStamp = forwardRef<HTMLButtonElement, InitialsStampProps>(
  function InitialsStamp({ userId, firstName, lastName, className, ...rest }, ref) {
    const ink = styles[`ink${stampInk(userId)}`];
    return (
      <button
        ref={ref}
        type="button"
        className={[styles.stamp, ink, className].filter(Boolean).join(" ")}
        aria-label={t("stamp.menu", { name: `${firstName} ${lastName}` })}
        {...rest}
      >
        {initialsOf(firstName, lastName)}
      </button>
    );
  },
);
