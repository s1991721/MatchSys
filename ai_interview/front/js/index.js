(() => {
  const reduceMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches;
  if (reduceMotion || !window.gsap || !window.ScrollTrigger) return;

  gsap.registerPlugin(ScrollTrigger);

  const chapters = [
    [
      "01 / 07",
      "INTERVIEW DESIGN",
      "AI面接官",
      "ポジションを作成すると、AIが最適な面接を設計します。",
    ],
    [
      "02 / 07",
      "QUESTION GENERATION",
      "質問を設計する",
      "職種に必要なスキルから、面接で確かめるべきことを導き出す。",
    ],
    [
      "03 / 07",
      "CANDIDATE ENTRY",
      "候補者が参加",
      "準備された面接に、候補者が接続します。",
    ],
    [
      "04 / 07",
      "AI INTERVIEW",
      "対話から見抜く",
      "一つひとつの回答を理解しながら、面接を進める。",
    ],
    [
      "05 / 07",
      "ADAPTIVE FOLLOW-UP",
      "回答を深掘りする",
      "決められた質問ではなく、その人の言葉から次の問いを生み出す。",
    ],
    [
      "06 / 07",
      "REAL-TIME ANALYSIS",
      "可能性を可視化",
      "対話の中から、思考と行動の特徴をリアルタイムに分析する。",
    ],
    [
      "07 / 07",
      "CANDIDATE REPORT",
      "判断できる評価へ",
      "面接の内容を、次の選考につながる評価として届ける。",
    ],
  ];
  const stops = [0, 0.16, 0.3, 0.38, 0.58, 0.72, 0.86];
  const navButtons = [...document.querySelectorAll(".step-nav button")];
  const chapterNo = document.querySelector(".chapter-no");
  const chapterKicker = document.querySelector(".chapter-kicker");
  const chapterTitle = document.querySelector(".chapter-heading h1");
  const chapterCopy = document.querySelector(".chapter-copy");
  const story = document.querySelector(".story");
  let activeStep = -1;

  function setChapter(index) {
    if (index === activeStep) return;
    activeStep = index;
    const content = chapters[index];
    gsap.to([chapterKicker, chapterTitle, chapterCopy], {
      opacity: 0,
      y: -8,
      duration: 0.16,
      overwrite: true,
      onComplete: () => {
        chapterNo.textContent = content[0];
        chapterKicker.textContent = content[1];
        chapterTitle.textContent = content[2];
        chapterCopy.textContent = content[3];
        gsap.fromTo(
          [chapterKicker, chapterTitle, chapterCopy],
          { opacity: 0, y: 8 },
          { opacity: 1, y: 0, duration: 0.3, stagger: 0.04, overwrite: true },
        );
      },
    });
    navButtons.forEach((button, i) =>
      button.classList.toggle("active", i === index),
    );
    document
      .querySelector(".generation-layer")
      .setAttribute("aria-hidden", index === 1 ? "false" : "true");
    document
      .querySelector(".candidate-stage")
      .setAttribute("aria-hidden", index >= 2 && index <= 5 ? "false" : "true");
    document
      .querySelector(".interview-ui")
      .setAttribute("aria-hidden", index === 3 ? "false" : "true");
    document
      .querySelector(".followup-ui")
      .setAttribute("aria-hidden", index === 4 ? "false" : "true");
    document
      .querySelector(".analysis-ui")
      .setAttribute("aria-hidden", index === 5 ? "false" : "true");
    document
      .querySelector(".report-ui")
      .setAttribute("aria-hidden", index === 6 ? "false" : "true");
  }

  function indexForProgress(progress) {
    let index = 0;
    for (let i = 1; i < stops.length; i += 1)
      if (progress >= stops[i]) index = i;
    return index;
  }

  gsap.set(
    [
      ".generation-layer",
      ".candidate-stage",
      ".interview-ui",
      ".followup-ui",
      ".analysis-ui",
      ".report-ui",
    ],
    { autoAlpha: 0 },
  );
  gsap.set(".field, .tags span", { opacity: 0, y: 14 });
  gsap.set(".question-bank article", { opacity: 0, x: 35 });
  gsap.set(".skill-bank span", { opacity: 0, x: -30 });
  gsap.set(".candidate-media img", {
    opacity: 0.12,
    filter: "blur(12px) saturate(.6) brightness(.45)",
  });
  gsap.set(".waiting-shade", { opacity: 1 });
  gsap.set(".answer-skills span", { opacity: 0, x: -25 });
  gsap.set(".followup-card", { opacity: 0, x: 35 });
  gsap.set(".metrics article", { opacity: 0, scale: 0.55 });
  gsap.set(".report-card", { opacity: 0, y: 45, scale: 0.94 });
  gsap.set(".report-card > div > *", { opacity: 0, y: 12 });

  const timeline = gsap.timeline({
    defaults: { ease: "none" },
    scrollTrigger: {
      trigger: story,
      start: "top top",
      end: "bottom bottom",
      scrub: 1,
      invalidateOnRefresh: true,
      onUpdate: (self) => {
        setChapter(indexForProgress(self.progress));
        gsap.set(".story-progress i", { scaleX: self.progress });
      },
    },
  });

  timeline
    .to(".scroll-cue", { autoAlpha: 0, duration: 0.15 }, 0)
    .to(".field", { opacity: 1, y: 0, duration: 0.28, stagger: 0.07 }, 0)
    .to(
      ".tags span",
      { opacity: 1, y: 0, duration: 0.28, stagger: 0.045 },
      0.22,
    )
    .to(
      ".briefcase",
      {
        boxShadow:
          "0 0 55px rgba(83,167,246,.48), inset 0 0 38px rgba(45,115,180,.28)",
        duration: 0.25,
      },
      0.45,
    )
    .to(".job-state p", { color: "#72d0b6", duration: 0.12 }, 0.58)
    .to(
      ".position-layer",
      { autoAlpha: 0, scale: 0.86, y: -35, duration: 0.38 },
      1.05,
    )
    .to(".generation-layer", { autoAlpha: 1, duration: 0.25 }, 1.1)
    .to(
      ".skill-bank span",
      { opacity: 1, x: 0, duration: 0.35, stagger: 0.08 },
      1.18,
    )
    .fromTo(
      ".ai-core",
      { scale: 0.45, rotation: -25 },
      { scale: 1, rotation: 0, duration: 0.52 },
      1.32,
    )
    .fromTo(
      ".energy-lines",
      { opacity: 0, scaleX: 0.2 },
      { opacity: 0.65, scaleX: 1, duration: 0.5 },
      1.5,
    )
    .to(
      ".question-bank article",
      { opacity: 1, x: 0, duration: 0.4, stagger: 0.12 },
      1.62,
    )
    .fromTo(
      ".ready-state",
      { opacity: 0, y: 10 },
      { opacity: 1, y: 0, duration: 0.25 },
      2.2,
    )
    .to(
      ".generation-layer",
      { autoAlpha: 0, scale: 0.92, duration: 0.35 },
      2.55,
    )
    .to(".candidate-stage", { autoAlpha: 1, duration: 0.3 }, 2.62)
    .fromTo(
      ".candidate-stage",
      { scale: 0.84 },
      { scale: 1, duration: 0.48 },
      2.62,
    )
    .to(".waiting-orbit", { rotation: 360, duration: 0.9 }, 2.68)
    .to(".waiting-copy", { opacity: 0, y: -8, duration: 0.18 }, 2.98)
    .to(".joined-copy", { opacity: 1, y: -8, duration: 0.22 }, 3.02)
    .to(
      ".candidate-media img",
      {
        opacity: 1,
        filter: "blur(0px) saturate(.92) brightness(.86)",
        duration: 0.5,
      },
      3.08,
    )
    .to(".waiting-shade", { opacity: 0.08, duration: 0.5 }, 3.08)
    .to(".waiting-state", { autoAlpha: 0, duration: 0.2 }, 3.4)
    .to(".video-name, .call-controls", { opacity: 1, duration: 0.25 }, 3.42)
    .to(".interview-ui", { autoAlpha: 1, duration: 0.3 }, 3.55)
    .fromTo(
      ".initial-prompt",
      { x: -35, opacity: 0 },
      { x: 0, opacity: 1, duration: 0.35 },
      3.62,
    )
    .fromTo(
      ".live-score",
      { x: 35, opacity: 0 },
      { x: 0, opacity: 1, duration: 0.35 },
      3.72,
    )
    .to(".live-ring", { "--live-angle": "295deg", duration: 0.65 }, 3.8)
    .to(".call-controls", { opacity: 0, duration: 0.18 }, 3.95)
    .to(".timer, .waveform", { opacity: 1, duration: 0.3 }, 4.0)
    .to(".candidate-stage", { scale: 1.035, duration: 0.5 }, 4.2)
    .to(".initial-prompt", { autoAlpha: 0, x: -25, duration: 0.3 }, 5.0)
    .to(".followup-ui", { autoAlpha: 1, duration: 0.28 }, 5.03)
    .to(
      ".answer-skills span",
      { opacity: 1, x: 0, duration: 0.35, stagger: 0.09 },
      5.08,
    )
    .to(".followup-card", { opacity: 1, x: 0, duration: 0.42 }, 5.32)
    .to(
      ".waveform",
      { filter: "drop-shadow(0 0 11px #68bcff)", scaleY: 1.18, duration: 0.45 },
      5.42,
    )
    .to(".live-ring", { "--live-angle": "305deg", duration: 0.3 }, 5.58)
    .to(".followup-ui, .live-score", { autoAlpha: 0, duration: 0.32 }, 6.35)
    .to(
      ".candidate-stage",
      { scale: 0.75, y: -75, opacity: 0.48, duration: 0.48 },
      6.38,
    )
    .to(".analysis-ui", { autoAlpha: 1, duration: 0.35 }, 6.45)
    .to(
      ".metrics article",
      { opacity: 1, scale: 1, duration: 0.4, stagger: 0.1 },
      6.55,
    )
    .to(".radar-shape", { scale: 1, duration: 0.62 }, 6.72)
    .fromTo(
      ".radar span",
      { opacity: 0 },
      { opacity: 1, duration: 0.25, stagger: 0.05 },
      6.86,
    )
    .to(".analysis-ui", { autoAlpha: 0, duration: 0.34 }, 7.52)
    .to(
      ".candidate-stage",
      { opacity: 0.08, scale: 0.64, filter: "blur(8px)", duration: 0.38 },
      7.52,
    )
    .to(".report-ui", { autoAlpha: 1, duration: 0.3 }, 7.58)
    .to(".report-card", { opacity: 1, y: 0, scale: 1, duration: 0.48 }, 7.62)
    .to(
      ".report-card > div > *",
      { opacity: 1, y: 0, duration: 0.35, stagger: 0.045 },
      7.78,
    )
    .fromTo(
      ".final-score strong",
      { textContent: 0 },
      { textContent: 84, duration: 0.55, snap: { textContent: 1 } },
      7.88,
    )
    .to(
      ".report-card",
      {
        boxShadow:
          "0 0 65px rgba(69,151,228,.16), 0 35px 100px rgba(0,0,0,.36)",
        duration: 0.45,
      },
      8.35,
    );

  gsap.to(".waveform", {
    scaleY: 1.35,
    duration: 0.42,
    repeat: -1,
    yoyo: true,
    ease: "sine.inOut",
  });
  gsap.to(".ambient i", {
    y: -22,
    opacity: 0.25,
    duration: 2.8,
    repeat: -1,
    yoyo: true,
    stagger: 0.35,
    ease: "sine.inOut",
  });
  gsap.to(".ai-core span:first-of-type", {
    rotation: 360,
    duration: 16,
    repeat: -1,
    ease: "none",
  });
  gsap.to(".ai-core span:last-of-type", {
    rotation: -360,
    duration: 24,
    repeat: -1,
    ease: "none",
  });

  navButtons.forEach((button, index) => {
    button.addEventListener("click", () => {
      const maxScroll = story.offsetHeight - window.innerHeight;
      window.scrollTo({
        top: story.offsetTop + maxScroll * stops[index],
        behavior: "smooth",
      });
    });
  });

  document
    .querySelector(".report-action button")
    .addEventListener("click", (event) => {
      event.currentTarget.textContent = "最終面接へ進めました";
      event.currentTarget.disabled = true;
    });

  setChapter(0);
})();
