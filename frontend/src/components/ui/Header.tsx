// import { useNavigate } from 'react-router-dom';
// import { useAuth } from '@/hooks/useAuth';
// import { Button } from '@/components/ui/Button';

// export const Header = () => {
//   const { user, logout } = useAuth();
//   const navigate = useNavigate();

//   const handleLogout = () => {
//     logout();
//     navigate('/login');
//   };

//   return (
//     <header className="bg-white border-b border-gray-200 px-4 py-3">
//       <div className="flex items-center justify-between max-w-7xl mx-auto">
//         <div className="flex items-center gap-3">
//           <span className="text-2xl">🎙️</span>
//           <h1 className="text-xl font-bold text-gray-900">Meeting Insight</h1>
//         </div>
        
//         <div className="flex items-center gap-4">
//           {user && (
//             <>
//               <span className="text-sm text-gray-600">
//                 {user.full_name || user.username}
//                 {user.role === 'admin' && (
//                   <span className="ml-2 px-2 py-0.5 text-xs bg-primary-100 text-primary-700 rounded-full">
//                     Админ
//                   </span>
//                 )}
//               </span>
//               <Button variant="ghost" size="sm" onClick={handleLogout}>
//                 Выйти
//               </Button>
//             </>
//           )}
//         </div>
//       </div>
//     </header>
//   );
// };