import { Link } from 'react-router-dom'
import EmptyState from '../../components/common/EmptyState.jsx'
import StatusBadge from '../../components/common/StatusBadge.jsx'
import { formatHorseGender } from '../../components/horse/horseLabels.js'

function OwnerHorses({ horses, currentUser, owners = [] }) {
  const currentOwnerId = currentUser?.id || ''
  const ownedHorses = horses.filter((horse) => String(horse.ownerUserId) === String(currentOwnerId))
  const owner = owners.find((item) => String(item.ownerId) === String(currentOwnerId)) || currentUser

  return (
    <main className="page-content">
      <nav className="breadcrumb" aria-label="Đường dẫn">Ngựa của tôi</nav>
      <header className="page-heading"><div><p className="eyebrow">CHỦ SỞ HỮU NGỰA · {owner?.fullName || 'CHỦ SỞ HỮU'}</p><h1>Ngựa của tôi</h1><p>Theo dõi hồ sơ và tình trạng sức khỏe của những ngựa thuộc sở hữu của bạn.</p></div></header>
      {ownedHorses.length === 0 ? <EmptyState title="Bạn chưa có ngựa nào trong hệ thống" description="Các ngựa thuộc quyền sở hữu của bạn sẽ xuất hiện tại đây." /> : (
        <div className="card-grid">
          {ownedHorses.map((horse) => <article className="panel horse-card" key={horse.id}>
            <span className="profile-id">Mã ngựa #{horse.code || horse.id}</span><h2>{horse.name}</h2><p>{horse.breed} · {formatHorseGender(horse.sex)}</p>
            <dl className="card-statuses"><div><dt>Trạng thái hồ sơ</dt><dd><StatusBadge status={horse.profileStatus} type="registration" /></dd></div><div><dt>Sức khỏe</dt><dd><StatusBadge status={horse.healthStatus} type="health" /></dd></div></dl>
            <Link className="button" to={`/owner/horses/${horse.id}`}>Mở hồ sơ và sức khỏe</Link>
          </article>)}
        </div>
      )}
    </main>
  )
}

export default OwnerHorses
