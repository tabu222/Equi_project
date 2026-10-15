import { Link } from 'react-router-dom'
import './LandingPage.css'

const roles = [
  {
    number: '01',
    title: 'Club Manager',
    subtitle: 'Quản lý câu lạc bộ',
    description:
      'Quản lý hồ sơ ngựa, chủ sở hữu, tiếp nhận và toàn bộ hoạt động vận hành của câu lạc bộ.',
  },
  {
    number: '02',
    title: 'Head Trainer',
    subtitle: 'Huấn luyện viên trưởng',
    description:
      'Xây dựng giáo án, theo dõi tiến độ và điều phối chương trình huấn luyện.',
  },
  {
    number: '03',
    title: 'Veterinarian',
    subtitle: 'Bác sĩ thú y',
    description:
      'Theo dõi sức khỏe, khám đầu vào và cập nhật tình trạng y tế của ngựa.',
  },
  {
    number: '04',
    title: 'Groom',
    subtitle: 'Nhân viên chăm sóc',
    description:
      'Theo dõi tình trạng hằng ngày và phối hợp cùng đội ngũ chuyên môn.',
  },
  {
    number: '05',
    title: 'Horse Owner',
    subtitle: 'Chủ sở hữu',
    description:
      'Theo dõi hồ sơ, trạng thái sức khỏe và tiến trình của ngựa trong câu lạc bộ.',
  },
]

const features = [
  {
    tag: 'HORSE PROFILE',
    title: 'Hồ sơ ngựa tập trung',
    description:
      'Tất cả thông tin nhận diện, dòng dõi, chủ sở hữu, tài liệu và trạng thái hồ sơ được quản lý tại một nơi.',
    icon: 'H',
  },
  {
    tag: 'TRAINING',
    title: 'Quản lý huấn luyện',
    description:
      'Lập kế hoạch, theo dõi tiến độ và đồng bộ thông tin giữa đội ngũ huấn luyện.',
    icon: 'T',
  },
  {
    tag: 'HEALTH',
    title: 'Theo dõi sức khỏe',
    description:
      'Hỗ trợ bác sĩ theo dõi hồ sơ khám, kết luận sức khỏe và điều kiện tập luyện.',
    icon: 'V',
  },
  {
    tag: 'WORKFLOW',
    title: 'Vận hành đồng bộ',
    description:
      'Mỗi vai trò nhìn thấy đúng dữ liệu cần thiết và phối hợp trên cùng một hệ thống.',
    icon: 'W',
  },
]

function ArrowIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="landing-arrow-icon"
    >
      <path
        d="M5 12h14M13 6l6 6-6 6"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function LandingPage() {
  return (
    <div className="landing-page">
      <header className="landing-nav">
        <Link className="landing-brand" to="/">
           <span className="landing-brand-mark">
    <img
      src="/equitrack-mark.jpg"
      alt="EquiTrack"
    />
  </span>

          <span>
            <strong>EQUITRACK</strong>
            <small>Racehorse performance</small>
          </span>
        </Link>

        <nav className="landing-nav-links">
          <a href="#about">Giới thiệu</a>
          <a href="#roles">Vai trò</a>
          <a href="#features">Tính năng</a>
          <a href="#workflow">Vận hành</a>
        </nav>

        <Link className="landing-login-button" to="/login">
          Đăng nhập
          <ArrowIcon />
        </Link>
      </header>

      <main>
        <section className="landing-hero">
          <div className="hero-background-orb hero-orb-one" />
          <div className="hero-background-orb hero-orb-two" />

          <div className="landing-hero-copy">
            <div className="landing-eyebrow">
              <span />
              RACEHORSE MANAGEMENT PLATFORM
            </div>

            <h1>
              Nền tảng quản lý
              <span>ngựa đua toàn diện.</span>
            </h1>

            <p className="landing-hero-description">
              Một không gian vận hành tập trung dành cho câu lạc bộ
              ngựa đua — từ hồ sơ, sức khỏe đến quá trình huấn luyện
              và phối hợp đội ngũ.
            </p>

            <div className="landing-hero-actions">
              <Link className="landing-primary-button" to="/login">
                Trải nghiệm hệ thống
                <ArrowIcon />
              </Link>

              <a className="landing-text-button" href="#features">
                Khám phá nền tảng
              </a>
            </div>

            <div className="landing-trust-row">
              <div>
                <strong>500+</strong>
                <span>Hồ sơ ngựa</span>
              </div>

              <div>
                <strong>50+</strong>
                <span>Câu lạc bộ</span>
              </div>

              <div>
                <strong>99.9%</strong>
                <span>Khả dụng hệ thống</span>
              </div>
            </div>
          </div>

          <div className="landing-hero-visual">
            <div className="hero-image-shell">
              <img
                src="/landing-horse.jpg"
                alt="Ngựa đua trong chuồng"
              />

              <div className="hero-image-overlay" />


            </div>

            <div className="floating-card floating-card-top">
              <span className="floating-card-icon">✓</span>

              <div>
                <small>Trạng thái sức khỏe</small>
                <strong>Sẵn sàng tập luyện</strong>
              </div>
            </div>

            <div className="floating-card floating-card-bottom">
              <div className="mini-chart">
                <span style={{ height: '38%' }} />
                <span style={{ height: '55%' }} />
                <span style={{ height: '46%' }} />
                <span style={{ height: '78%' }} />
                <span style={{ height: '66%' }} />
                <span style={{ height: '92%' }} />
              </div>

              <div>
                <small>Training Performance</small>
                <strong>+18.4%</strong>
              </div>
            </div>
          </div>


        </section>

        <section className="landing-marquee">
          <div>
            <span>HORSE PROFILE</span>
            <i />
            <span>TRAINING MANAGEMENT</span>
            <i />
            <span>HEALTH MONITORING</span>
            <i />
            <span>OWNER EXPERIENCE</span>
            <i />
            <span>CLUB OPERATIONS</span>
          </div>
        </section>

        <section id="about" className="landing-about">
          <div className="landing-section-number"></div>

          <div className="landing-about-heading">
            <p className="landing-section-label">
              MỘT NỀN TẢNG. MỘT HỆ THỐNG.
            </p>

            <h2>
              Được thiết kế cho toàn bộ
              <span>vòng đời vận hành ngựa đua.</span>
            </h2>
          </div>

          <div className="landing-about-description">
            <p>
              EquiTrack kết nối dữ liệu hồ sơ, sức khỏe và huấn luyện
              để mỗi thành viên trong câu lạc bộ có thể làm việc trên
              cùng một nguồn thông tin.
            </p>

            <p>
              Không còn dữ liệu rời rạc giữa nhiều bộ phận. Thông tin
              quan trọng được cập nhật xuyên suốt và hiển thị theo đúng
              quyền của từng vai trò.
            </p>
          </div>
        </section>

        <section id="roles" className="landing-roles">
          <header className="landing-section-header">
            <div>
              <p className="landing-section-label">
                ROLE-BASED EXPERIENCE
              </p>

              <h2>
                5 vai trò.
                <span>Một hệ thống thống nhất.</span>
              </h2>
            </div>

            <p>
              Mỗi vai trò có khu vực làm việc riêng nhưng tất cả đều
              vận hành trên cùng một nền tảng dữ liệu.
            </p>
          </header>

          <div className="roles-grid">
            {roles.map((role) => (
              <article className="role-card" key={role.number}>
                <div className="role-card-top">
  <span>{role.number}</span>
</div>

                <div>
                  <p>{role.subtitle}</p>
                  <h3>{role.title}</h3>
                </div>

                <p className="role-description">
                  {role.description}
                </p>
              </article>
            ))}
          </div>
        </section>

        <section id="features" className="landing-features">
          <div className="features-intro">
            <p className="landing-section-label">
              BUILT FOR PERFORMANCE
            </p>

            <h2>
              Tập trung vào
              <span>những điều thực sự quan trọng.</span>
            </h2>

            <p>
              Một giao diện rõ ràng giúp đội ngũ tập trung vào quyết
              định chuyên môn thay vì mất thời gian tìm kiếm dữ liệu.
            </p>
          </div>

          <div className="feature-list">
            {features.map((feature, index) => (
             <article className="feature-row" key={feature.title}>
  <div className="feature-number-box">
    <span>0{index + 1}</span>
  </div>

  <div className="feature-copy">
    <small>{feature.tag}</small>

    <h3>
      {feature.title}
    </h3>

    <p>
      {feature.description}
    </p>
  </div>
</article>
            ))}
          </div>
        </section>

        <section id="workflow" className="landing-workflow">
          <div className="workflow-visual">
            <div className="workflow-dashboard">
              <div className="workflow-dashboard-bar">
                <span />
                <span />
                <span />
              </div>

              <div className="workflow-dashboard-content">
                <aside>
                  <div className="mock-logo">
  <img
    src="/equitrack-mark.jpg"
    alt="EquiTrack"
  />
</div>
                  <div className="mock-menu active" />
                  <div className="mock-menu" />
                  <div className="mock-menu" />
                  <div className="mock-menu short" />
                </aside>

                <div className="mock-main">
                  <div className="mock-title" />

                  <div className="mock-stat-grid">
                    <div />
                    <div />
                    <div />
                  </div>

                  <div className="mock-chart">
                    <span style={{ height: '34%' }} />
                    <span style={{ height: '48%' }} />
                    <span style={{ height: '42%' }} />
                    <span style={{ height: '65%' }} />
                    <span style={{ height: '57%' }} />
                    <span style={{ height: '80%' }} />
                    <span style={{ height: '71%' }} />
                    <span style={{ height: '92%' }} />
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="workflow-copy">
            <p className="landing-section-label">
              CONNECTED WORKFLOW
            </p>

            <h2>
              Dữ liệu thay đổi.
              <span>Giao diện cập nhật.</span>
            </h2>

            <p>
              Từ lúc ngựa được tiếp nhận, khám sức khỏe cho đến khi
              bước vào chương trình huấn luyện, trạng thái được cập
              nhật xuyên suốt giữa các vai trò.
            </p>

            <div className="workflow-points">
              <div>
                <span>01</span>
                <p>
                  Hồ sơ được tiếp nhận và xác minh bởi Club Manager.
                </p>
              </div>

              <div>
                <span>02</span>
                <p>
                  Veterinarian thực hiện khám và cập nhật sức khỏe.
                </p>
              </div>

              <div>
                <span>03</span>
                <p>
                  Kết quả được phản ánh đến Manager và Horse Owner.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="landing-cta">
          <div className="cta-glow" />

          <p className="landing-section-label">
            READY TO START?
          </p>

          <h2>
            Một nền tảng tốt hơn cho
            <span>những chiến mã tốt hơn.</span>
          </h2>

          <p>
            Quản lý câu lạc bộ, hồ sơ ngựa và hoạt động chuyên môn
            trên một hệ thống thống nhất.
          </p>

<Link
  className="landing-primary-button"
  to="/login"
  onClick={() => {
    window.location.href = '/login'
  }}
>
  Đăng nhập hệ thống
  <ArrowIcon />
</Link>
        </section>
      </main>

      <footer className="landing-footer">
        <div>
          <Link className="landing-brand" to="/">
            <span className="landing-brand-mark">
    <img
      src="/equitrack-mark.jpg"
      alt="EquiTrack logo"
    />
  </span>

            <span>
              <strong>EQUITRACK</strong>
              <small>Racehorse performance</small>
            </span>
          </Link>

          <p>
            Racehorse Training & Management System.
          </p>
        </div>

        <div className="footer-links">
          <a href="#about">Giới thiệu</a>
          <a href="#roles">Vai trò</a>
          <a href="#features">Tính năng</a>
          <Link to="/login">Đăng nhập</Link>
        </div>

        <div className="footer-bottom">
          <span>© 2026 EQUITRACK</span>
        </div>
      </footer>
    </div>
  )
}

export default LandingPage