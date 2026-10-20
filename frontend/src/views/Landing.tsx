import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { api } from '../lib/api';

export function Landing() {
  const navigate = useNavigate();
  const [openRoles, setOpenRoles] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.candidate
      .searchJobs({ page: 1, pageSize: 1 })
      .then((page) => {
        if (!cancelled) setOpenRoles(page.total);
      })
      .catch(() => {
        if (!cancelled) setOpenRoles(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="landing">
      <section className="hero">
        <div className="hero__glow hero__glow--a" aria-hidden="true" />
        <div className="hero__glow hero__glow--b" aria-hidden="true" />

        <div className="hero__copy">
          <p className="hero__badge">
            <span className="hero__dot" aria-hidden="true" />
            {openRoles === null ? 'Hiring now' : `${openRoles.toLocaleString()} open roles`}
          </p>

          <h1 className="hero__title">
            Good work finds good people.
          </h1>

          <p className="hero__lead">
            Jaagir brings hiring teams and job seekers together in one calm place. Post a role in
            minutes, or find the next step in your career.
          </p>

          <div className="hero__actions">
            <button type="button" className="cta cta--primary" onClick={() => navigate('/jobs')}>
              Find a job
            </button>
            <button type="button" className="cta cta--ghost" onClick={() => navigate('/employers')}>
              Post a job
            </button>
          </div>

          <dl className="hero__facts">
            <div>
              <dt>Search</dt>
              <dd>Every open role, one search box</dd>
            </div>
            <div>
              <dt>Apply</dt>
              <dd>One click, no forms to repeat</dd>
            </div>
            <div>
              <dt>Track</dt>
              <dd>Every application in one list</dd>
            </div>
          </dl>
        </div>

        <div className="hero__art" aria-hidden="true">
          <div className="ghostcard ghostcard--back">
            <span className="ghostcard__line" />
            <span className="ghostcard__line ghostcard__line--short" />
          </div>
          <div className="ghostcard ghostcard--mid">
            <span className="ghostcard__tag" />
            <span className="ghostcard__line" />
            <span className="ghostcard__line ghostcard__line--short" />
          </div>
          <div className="ghostcard ghostcard--front">
            <span className="ghostcard__pin">New</span>
            <strong className="ghostcard__title">Product Designer</strong>
            <span className="ghostcard__meta">Remote · Full time</span>
            <span className="ghostcard__chips">
              <span>Figma</span>
              <span>Research</span>
              <span>Systems</span>
            </span>
            <span className="ghostcard__cta">Apply</span>
          </div>
        </div>
      </section>

      <section className="roles" aria-label="Choose how you want to use Jaagir">
        <article className="role">
          <span className="role__icon role__icon--seek" aria-hidden="true">
            ⌕
          </span>
          <h2 className="role__title">I am looking for work</h2>
          <p className="role__text">
            Browse roles that match your skills, apply with your profile, and follow every
            application from one place.
          </p>
          <button type="button" className="role__link" onClick={() => navigate('/jobs')}>
            Browse jobs
            <span aria-hidden="true">→</span>
          </button>
        </article>

        <article className="role">
          <span className="role__icon role__icon--hire" aria-hidden="true">
            ✦
          </span>
          <h2 className="role__title">I am hiring</h2>
          <p className="role__text">
            Write a role once, publish it with one click, and read every applicant in a single
            list.
          </p>
          <button type="button" className="role__link" onClick={() => navigate('/employers')}>
            Post a job
            <span aria-hidden="true">→</span>
          </button>
        </article>
      </section>

      <section className="how" aria-label="How Jaagir works">
        <h2 className="how__title">Three steps, no noise</h2>
        <ol className="how__steps">
          <li>
            <span className="how__num">1</span>
            <strong>Create your profile</strong>
            <p>Name, headline, skills, and a link to your resume.</p>
          </li>
          <li>
            <span className="how__num">2</span>
            <strong>Find a role</strong>
            <p>Search by title, skill, place, or type of work.</p>
          </li>
          <li>
            <span className="how__num">3</span>
            <strong>Apply and track</strong>
            <p>Send one application and watch its status change.</p>
          </li>
        </ol>
      </section>
    </div>
  );
}
