export interface VoiceProfile {
  has_profile: boolean;
  created_at: string | null;
  full_name?: string;
  embedding_dim?: number;
}

export interface EnrolledSpeaker {
  user_id: string;
  full_name: string;
  has_embedding: boolean;
}

export interface EnrolledSpeakers {
  speakers: EnrolledSpeaker[];
  count: number;
}

export interface VoiceStats {
  enrolled_count: number;
  error?: string;
}

export interface UserProfile {
  user_id: string;
  username: string;
  surname: string;
  name: string;
  patronymic: string;
  full_name: string;
  email: string;
  avatar_url: string | null;
}

export interface UpdateProfileData {
  surname?: string;
  name?: string;
  patronymic?: string;
  email?: string;
}