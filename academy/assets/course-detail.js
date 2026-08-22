(() => {
  const page = document.getElementById("coursePage");
  const courseData = window.AcademyCourseData;

  const getSelectedCourse = () => {
    const params = new URLSearchParams(window.location.search);
    const requestedKey = params.get("course");
    const courseKey = requestedKey
      ? requestedKey.trim().toLowerCase()
      : courseData.defaultCourseKey;

    const course = courseData.courses[courseKey];
    return course ? { courseKey, course } : null;
  };

  const createPlayIcon = () => {
    const wrapper = document.createElement("span");
    wrapper.className = "lesson-play";
    wrapper.setAttribute("aria-hidden", "true");
    wrapper.innerHTML = '<svg viewBox="0 0 10 10" fill="currentColor"><path d="m3 2 5 3-5 3z"/></svg>';
    return wrapper;
  };

  const createChapter = (title, index) => {
    const number = String(index + 1).padStart(2, "0");
    const lesson = document.createElement("div");
    lesson.className = "lesson";

    const numberElement = document.createElement("span");
    numberElement.className = "lesson-number";
    numberElement.textContent = number;

    const titleElement = document.createElement("span");
    titleElement.className = "lesson-title";
    titleElement.textContent = title;

    lesson.append(createPlayIcon(), numberElement, titleElement);
    return lesson;
  };

  const renderCourse = (course, courseKey) => {
    document.title = `${course.title} | AOMERA Academy`;
    document.getElementById("breadcrumbTitle").textContent = course.title;
    document.getElementById("courseTitle").textContent = course.title;
    document.getElementById("courseDescription").textContent = course.description;
    document.getElementById("courseCover").dataset.course = courseKey;
    const coverImage = document.getElementById("courseLogo");
    coverImage.addEventListener("error", () => coverImage.hidden = true, { once: true });
    coverImage.alt = `${course.title} コースカバー`;
    coverImage.src = course.cover;

    const startButton = document.getElementById("startButton");
    startButton.href = course.link;
    if (course.type === "external") {
      startButton.textContent = "外部サイトで学習する ↗";
      startButton.target = "_blank";
      startButton.rel = "noopener noreferrer";
    }

    const lessonList = document.getElementById("lessonList");
    const chapters = document.createDocumentFragment();
    course.chapters.forEach((chapter, index) => chapters.append(createChapter(chapter, index)));
    lessonList.replaceChildren(chapters);
  };

  const renderNotFound = () => {
    document.title = "コースが見つかりません | AOMERA Academy";
    const section = document.createElement("section");
    section.className = "not-found";
    section.innerHTML = '<h1>コースが見つかりません</h1><p>指定されたコースは存在しないか、公開を終了しています。</p><a class="start-button" href="index.html#courses">コース一覧へ戻る</a>';
    page.replaceChildren(section);
  };

  if (!page || !courseData) return;

  const selection = getSelectedCourse();
  if (selection) {
    renderCourse(selection.course, selection.courseKey);
  } else {
    renderNotFound();
  }
})();
