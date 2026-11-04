# Навчальні матеріали — Cloudinary (без R2)

Підключено Cloudinary cloud name `mctk9huf` та unsigned upload preset `tech_training_upload` у гілці `feature/netlify-frontend`.

1. У Cloudflare D1 (`TASKS_DB`) виконайте `migrations/0002_training_materials.sql` (користувач уже повідомив про виконання).
2. Cloudinary → Settings → Upload → Upload presets: preset `tech_training_upload` має бути **Unsigned**, з обмеженням форматів і розміру. Cloudinary може вимагати окремо дозволити завантаження відео.
3. Дочекайтесь Cloudflare Pages deploy гілки `feature/netlify-frontend`.
4. У «База даних → Навчальні матеріали» бос створює та публікує інструкції. Менеджери читають опубліковані матеріали.

Файли завантажуються безпосередньо з браузера в Cloudinary; D1 зберігає посилання. Ключі API та картка не потрібні для цієї схеми. YouTube/Vimeo також підтримуються.

**Безпека:** unsigned preset доступний будь-кому, хто дізнався його назву та cloud name; авторизація сайту не захищає сам upload endpoint. Медіа за Cloudinary URL потенційно публічні. Не завантажуйте конфіденційні матеріали. У Cloudinary preset обмежте типи, розмір і, за можливості, папку/квоти; слідкуйте за використанням безкоштовного плану. Для повністю приватних файлів потрібна інша архітектура (серверне підписування та приватна доставка).

Видалення інструкції не видаляє файли з Cloudinary автоматично; їх можна прибрати вручну у Media Library. Ліміт клієнта 50 МБ, але Cloudinary може встановлювати менший ліміт для unsigned upload. Попередні R2 endpoint-и збережено для сумісності, але R2 binding не потрібен для нових матеріалів.
